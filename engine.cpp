// SPDX-FileCopyrightText: 2026 seekgirl
// SPDX-License-Identifier: GPL-3.0-or-later

#include "server/StdInc.h"
#include "server/CGameHandler.h"
#include "server/IGameServer.h"
#include "server/ServerSpellCastEnvironment.h"
#include "server/TurnTimerHandler.h"
#include "server/battles/BattleProcessor.h"
#include "server/processors/HeroPoolProcessor.h"
#include "server/processors/NewTurnProcessor.h"
#include "server/processors/PlayerMessageProcessor.h"
#include "server/processors/TurnOrderProcessor.h"
#include "server/queries/QueriesProcessor.h"

#include "lib/CCreatureHandler.h"
#include "lib/CSkillHandler.h"
#include "lib/CPlayerState.h"
#include "lib/GameConstants.h"
#include "lib/GameLibrary.h"
#include "lib/callback/GameRandomizer.h"
#include "lib/filesystem/Filesystem.h"
#include "lib/gameState/CGameState.h"
#include "lib/gameState/GameStatistics.h"
#include "lib/json/JsonNode.h"
#include "lib/logging/CLogger.h"
#include "lib/mapObjects/CGHeroInstance.h"
#include "lib/mapObjects/army/CStackInstance.h"
#include "lib/mapping/CMap.h"
#include "lib/modding/ModIncompatibility.h"
#include "lib/networkPacks/PacksForClient.h"
#include "lib/networkPacks/StackLocation.h"
#include "lib/serializer/CLoadFile.h"
#include "lib/serializer/CSaveFile.h"
#include "lib/serializer/ESerializationVersion.h"
#include "lib/spells/CSpellHandler.h"

#include <boost/filesystem.hpp>

#include <cstdint>
#include <array>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{

constexpr int SAVE_VERSION = 902;
static_assert(static_cast<int>(ESerializationVersion::CURRENT) == SAVE_VERSION,
	"this editor must be rebuilt against a VCMI tree whose current save format is 902");

class OfflineServer final : public IGameServer
{
public:
	 explicit OfflineServer(const std::shared_ptr<CGameState> & state)
		: state(state)
	{}

	void setState(EServerState value) override
	{
		serverState = value;
	}

	EServerState getState() const override
	{
		return serverState;
	}

	bool isPlayerHost(const PlayerColor &) const override
	{
		return false;
	}

	bool hasPlayerAt(PlayerColor, GameConnectionID) const override
	{
		return false;
	}

	bool hasBothPlayersAtSameConnection(PlayerColor, PlayerColor) const override
	{
		return false;
	}

	void applyPack(CPackForClient & pack) override
	{
		if (!state)
			throw std::runtime_error("offline server has no game state");
		state->apply(pack);
	}

	void sendPack(CPackForClient &, GameConnectionID) override
	{
		// There are no clients in the offline editor.
	}

private:
	std::shared_ptr<CGameState> state;
	EServerState serverState = EServerState::GAMEPLAY;
};

struct LoadedGame
{
	std::shared_ptr<CGameState> state;
	OfflineServer server;
	std::unique_ptr<CGameHandler> handler;

	LoadedGame()
		: state(std::make_shared<CGameState>())
		, server(state)
		, handler(std::make_unique<CGameHandler>(server, state))
	{}
};

void configureLogging()
{
	auto * logger = CLogger::getGlobalLogger();
	logger->clearTargets();
	auto target = std::make_unique<CLogConsoleTarget>(nullptr);
	target->setColoredOutputEnabled(false);
	// The console target routes warnings and errors to stderr. Suppress INFO
	// and DEBUG messages so stdout remains a JSON-only channel.
	target->setThreshold(ELogLevel::WARN);
	logger->addTarget(std::move(target));
}

void initializeLibrary()
{
	configureLogging();
	const char * configuredApp = std::getenv("VCMI_APP_PATH");
	const boost::filesystem::path appDirectory = configuredApp && *configuredApp
		? boost::filesystem::path(configuredApp)
		: boost::filesystem::path("/Applications/VCMI.app");
	if (!boost::filesystem::exists(appDirectory) || !boost::filesystem::is_directory(appDirectory))
		throw std::runtime_error("VCMI application directory is unavailable (VCMI_APP_PATH): " + appDirectory.string());
	const boost::filesystem::path executableDirectory = appDirectory / "Contents" / "MacOS";
	if (!boost::filesystem::exists(executableDirectory))
		throw std::runtime_error("VCMI application directory is unavailable: " + executableDirectory.string());
	boost::filesystem::current_path(executableDirectory);

	if (LIBRARY)
		throw std::runtime_error("VCMI library has already been initialized");
	LIBRARY = new GameLibrary;
	try
	{
		LIBRARY->initializeFilesystem(false);
		LIBRARY->initializeLibrary();
	}
	catch (...)
	{
		delete LIBRARY;
		LIBRARY = nullptr;
		throw;
	}
}

void shutdownLibrary()
{
	if (!LIBRARY)
		return;
	CResourceHandler::destroy();
	delete LIBRARY;
	LIBRARY = nullptr;
}

void requireInputFile(const boost::filesystem::path & input)
{
	if (!boost::filesystem::exists(input))
		throw std::runtime_error("input file does not exist: " + input.string());
	if (!boost::filesystem::is_regular_file(input))
		throw std::runtime_error("input path is not a regular file: " + input.string());
}

void requireNewOutput(const boost::filesystem::path & input, const boost::filesystem::path & output)
{
	if (boost::filesystem::exists(output))
		throw std::runtime_error("refusing to overwrite existing output: " + output.string());

	if (input == output)
		throw std::runtime_error("input and output paths must be different");
}

std::string readTextFile(const boost::filesystem::path & path)
{
	std::ifstream stream(path.string(), std::ios::binary);
	if (!stream)
		throw std::runtime_error("cannot open patch file: " + path.string());

	return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

JsonNode readJsonFile(const boost::filesystem::path & path)
{
	const std::string contents = readTextFile(path);
	if (contents.empty())
		throw std::runtime_error("patch file is empty: " + path.string());

	JsonParsingSettings settings;
	settings.mode = JsonParsingSettings::JsonFormatMode::JSON;
	settings.strict = true;
	return JsonNode(contents.data(), contents.size(), settings, path.string());
}

si64 requiredInteger(const JsonNode & node, const std::string & field)
{
	if (!node.isNumber() || node.getType() != JsonNode::JsonType::DATA_INTEGER)
		throw std::runtime_error("patch field must be an integer: " + field);
	return node.Integer();
}

bool optionalBoolean(const JsonNode & node, const std::string & field, bool defaultValue)
{
	if (node.isNull())
		return defaultValue;
	if (!node.isBool())
		throw std::runtime_error("patch field must be a boolean: " + field);
	return node.Bool();
}

int checkedInt(si64 value, const std::string & field)
{
	if (value < std::numeric_limits<int>::min() || value > std::numeric_limits<int>::max())
		throw std::runtime_error("patch integer is out of range: " + field);
	return static_cast<int>(value);
}

std::unique_ptr<LoadedGame> loadGame(const boost::filesystem::path & path)
{
	requireInputFile(path);
	auto result = std::make_unique<LoadedGame>();
	CLoadFile loadFile(path, result->state.get());
	if (!loadFile.hasFeature(ESerializationVersion::CURRENT))
		throw std::runtime_error("only VCMI save format version 902 is supported");

	// Keep this order in sync with CGameHandler's save/load path: the game
	// state is deserialized first, followed by the server-side state.
	result->state->loadGame(loadFile);
	loadFile.load(*result->handler);
	result->state->preInit(LIBRARY);
	return result;
}

int humanPlayerCount(const CGameState & state)
{
	int count = 0;
	for (const auto & entry : state.players)
		if (entry.second.human)
			++count;
	return count;
}

void requireEditableGame(const CGameState & state)
{
	if (!state.currentBattles.empty())
		throw std::runtime_error("battle saves cannot be edited");
	if (humanPlayerCount(state) > 1)
		throw std::runtime_error("saves with multiple human players cannot be edited");
}

JsonNode makeArmyEntry(const SlotID & slot, const CStackInstance & stack)
{
	JsonNode result;
	result["slot"].Integer() = slot.getNum();
	result["creature"].Integer() = stack.getCreatureID().getNum();
	result["count"].Integer() = stack.getCount();
	return result;
}

JsonNode inspectGame(const CGameState & state)
{
	JsonNode result;
	result["version"].Integer() = SAVE_VERSION;
	result["day"].Integer() = state.day;

	for (const auto & item : state.players)
	{
		JsonNode player;
		player["color"].Integer() = item.first.getNum();
		player["human"].Bool() = item.second.human;
		player["cheated"].Bool() = item.second.cheated;
		player["status"].Integer() = static_cast<int>(item.second.status);
		player["enteredWinningCheatCode"].Bool() = item.second.enteredWinningCheatCode;
		player["enteredLosingCheatCode"].Bool() = item.second.enteredLosingCheatCode;
		result["players"].Vector().push_back(std::move(player));
	}

	auto & heroes = result["heroes"].Vector();
	for (const CGHeroInstance * hero : state.getMap().getObjects<CGHeroInstance>())
	{
		JsonNode entry;
		entry["id"].Integer() = hero->id.getNum();
		entry["name"].String() = hero->getNameTranslated();
		entry["owner"].Integer() = hero->getOwner().getNum();
		entry["attack"].Integer() = hero->getBasePrimarySkillValue(PrimarySkill::ATTACK);
		entry["defense"].Integer() = hero->getBasePrimarySkillValue(PrimarySkill::DEFENSE);
		entry["power"].Integer() = hero->getBasePrimarySkillValue(PrimarySkill::SPELL_POWER);
		entry["knowledge"].Integer() = hero->getBasePrimarySkillValue(PrimarySkill::KNOWLEDGE);
		entry["mana"].Integer() = hero->mana;

		bool cheated = false;
		bool human = false;
		const auto player = state.players.find(hero->getOwner());
		if (player != state.players.end())
		{
			human = player->second.human;
			cheated = player->second.cheated;
		}
		entry["cheated"].Bool() = cheated;
		entry["human"].Bool() = human;
		entry["spellbook"].Bool() = hero->hasSpellbook();
		auto & skills = entry["skills"].Vector();
		for (const auto & skill : hero->secSkills)
		{
			// A NONE/-1 pair is VCMI's internal marker for default hero-type
			// skills. preInit normally resolves it, but it is not a learned skill
			// and must not be exposed as an editable entry.
			if (skill.first == SecondarySkill::NONE)
				continue;

			JsonNode skillNode;
			skillNode["id"].Integer() = skill.first.getNum();
			skillNode["level"].Integer() = skill.second;
			skills.push_back(std::move(skillNode));
		}
		auto & spells = entry["spells"].Vector();
		for (const SpellID & spell : hero->getSpellsInSpellbook())
		{
			JsonNode spellNode;
			spellNode.Integer() = spell.getNum();
			spells.push_back(std::move(spellNode));
		}

		auto & army = entry["army"].Vector();
		for (const auto & slot : hero->Slots())
			if (slot.second)
				army.push_back(makeArmyEntry(slot.first, *slot.second));

		heroes.push_back(std::move(entry));
	}

	auto & skills = result["skills"].Vector();
	for (const auto & skill : LIBRARY->skillh->objects)
	{
		if (!skill)
			continue;

		JsonNode entry;
		entry["id"].Integer() = skill->getId().getNum();
		entry["name"].String() = skill->getNameTranslated();
		skills.push_back(std::move(entry));
	}

	auto & creatures = result["creatures"].Vector();
	for (size_t index = 0; index < LIBRARY->creh->objects.size(); ++index)
	{
		const auto & creature = LIBRARY->creh->objects[index];
		if (!creature)
			continue;

		JsonNode entry;
		entry["id"].Integer() = static_cast<si64>(index);
		entry["name"].String() = creature->getNamePluralTranslated();
		creatures.push_back(std::move(entry));
	}

	return result;
}

CGHeroInstance * findHumanHero(CGameState & state, int heroId)
{
	auto * hero = state.getHero(ObjectInstanceID(heroId));
	if (!hero)
		throw std::runtime_error("hero id does not identify a hero on the map: " + std::to_string(heroId));

	const auto player = state.players.find(hero->getOwner());
	if (player == state.players.end() || !player->second.human)
		throw std::runtime_error("only a hero owned by a human player can be edited");
	return hero;
}

struct ArmyEdit
{
	int slot = 0;
	int creature = 0;
	int count = 0;
};

struct SkillEdit
{
	int id = 0;
	int level = 0;
};

std::vector<SkillEdit> parseSkills(const JsonNode & node)
{
	if (!node.isVector())
		throw std::runtime_error("patch field must be a skills array: skills");

	std::vector<SkillEdit> result;
	std::set<int> seenSkills;
	for (const auto & item : node.Vector())
	{
		if (!item.isStruct())
			throw std::runtime_error("each skills entry must be an object");

		SkillEdit edit;
		edit.id = checkedInt(requiredInteger(item["id"], "skills.id"), "skills.id");
		edit.level = checkedInt(requiredInteger(item["level"], "skills.level"), "skills.level");
		if (edit.id < 0 || static_cast<size_t>(edit.id) >= LIBRARY->skillh->objects.size()
			|| !LIBRARY->skillh->objects[edit.id])
			throw std::runtime_error("skills id is invalid: " + std::to_string(edit.id));
		if (edit.level < 1 || edit.level > 3)
			throw std::runtime_error("skills level must be between 1 and 3");
		if (!seenSkills.insert(edit.id).second)
			throw std::runtime_error("skills contains a duplicate id: " + std::to_string(edit.id));
		result.push_back(edit);
	}
	return result;
}

std::vector<ArmyEdit> parseArmy(const JsonNode & node)
{
	if (!node.isVector())
		throw std::runtime_error("patch field must be an army array: army");

	std::vector<ArmyEdit> result;
	std::set<int> seenSlots;
	bool hasPositiveStack = false;
	for (const auto & item : node.Vector())
	{
		if (!item.isStruct())
			throw std::runtime_error("each army entry must be an object");

		ArmyEdit edit;
		edit.slot = checkedInt(requiredInteger(item["slot"], "army.slot"), "army.slot");
		edit.creature = checkedInt(requiredInteger(item["creature"], "army.creature"), "army.creature");
		edit.count = checkedInt(requiredInteger(item["count"], "army.count"), "army.count");
		if (edit.slot < 0 || edit.slot >= GameConstants::ARMY_SIZE)
			throw std::runtime_error("army slot is out of range: " + std::to_string(edit.slot));
		if (!seenSlots.insert(edit.slot).second)
			throw std::runtime_error("army contains a duplicate slot: " + std::to_string(edit.slot));
		if (edit.count < 0)
			throw std::runtime_error("army count cannot be negative");
		if (edit.count > 0)
		{
			hasPositiveStack = true;
			if (edit.creature < 0 || static_cast<size_t>(edit.creature) >= LIBRARY->creh->objects.size()
				|| !LIBRARY->creh->objects[edit.creature])
				throw std::runtime_error("army creature id is invalid: " + std::to_string(edit.creature));
		}
		result.push_back(edit);
	}
	if (!hasPositiveStack)
		throw std::runtime_error("army must contain at least one stack with a positive count");
	return result;
}

void applyArmy(CGameState & state, CGHeroInstance * hero, const std::vector<ArmyEdit> & edits)
{
	std::map<int, const ArmyEdit *> requested;
	for (const ArmyEdit & edit : edits)
		requested.emplace(edit.slot, &edit);
	std::vector<SlotID> existing;
	for (const auto & slot : hero->Slots())
		existing.push_back(slot.first);

	// Keep existing stack instances whenever possible. In particular, changing
	// only a quantity is applied as a state pack so stack experience and
	// creature-slot artifacts remain attached to the original instance.
	for (const SlotID & slotId : existing)
	{
		const auto requestedSlot = requested.find(slotId.getNum());
		if (requestedSlot == requested.end() || requestedSlot->second->count == 0)
		{
			hero->eraseStack(slotId);
			continue;
		}

		const ArmyEdit & edit = *requestedSlot->second;
		const auto * currentStack = hero->getStackPtr(slotId);
		if (currentStack->getCreatureID().getNum() == edit.creature)
		{
			if (currentStack->getCount() != edit.count)
			{
				ChangeStackCount change;
				change.army = hero->id;
				change.slot = slotId;
				change.count = edit.count;
				change.mode = ChangeValueMode::ABSOLUTE;
				state.apply(change);
			}
			continue;
		}

		hero->eraseStack(slotId);
		if (!hero->setCreature(slotId, CreatureID(edit.creature), edit.count))
			throw std::runtime_error("failed to replace army slot " + std::to_string(edit.slot));
	}

	for (const ArmyEdit & edit : edits)
	{
		if (edit.count == 0 || hero->hasStackAtSlot(SlotID(edit.slot)))
			continue;
		if (!hero->setCreature(SlotID(edit.slot), CreatureID(edit.creature), edit.count))
			throw std::runtime_error("failed to write army slot " + std::to_string(edit.slot));
	}
}

void applySkills(CGHeroInstance * hero, const std::vector<SkillEdit> & edits)
{
	std::set<int> requested;
	for (const SkillEdit & edit : edits)
		requested.insert(edit.id);

	// Remove skills that are absent from the requested final list first. Work
	// from a snapshot because setSecSkillLevel mutates secSkills in place.
	std::vector<SecondarySkill> existing;
	for (const auto & skill : hero->secSkills)
	{
		if (skill.first != SecondarySkill::NONE)
			existing.push_back(skill.first);
	}
	for (const SecondarySkill & skill : existing)
	{
		if (!requested.count(skill.getNum()))
			hero->setSecSkillLevel(skill, 0, ChangeValueMode::ABSOLUTE);
	}

	// Existing skills keep their position; new skills are appended in the
	// order supplied by the patch.
	for (const SkillEdit & edit : edits)
		hero->setSecSkillLevel(SecondarySkill(edit.id), edit.level, ChangeValueMode::ABSOLUTE);
}

void applyAllSpells(CGameHandler & handler, CGHeroInstance * hero)
{
	if (!hero->hasSpellbook()
		&& !handler.giveHeroNewArtifact(hero, ArtifactID::SPELLBOOK, ArtifactPosition::SPELLBOOK))
		throw std::runtime_error("failed to give the hero a spellbook");

	ChangeSpells change;
	change.learn = 1;
	change.hid = hero->id;
	for (const auto & spell : LIBRARY->spellh->objects)
	{
		if (!spell || spell->isSpecial() || spell->isCreatureAbility())
			continue;
		change.spells.insert(spell->getId());
	}
	handler.sendAndApply(change);
}

void applyPatch(LoadedGame & game, const JsonNode & patch)
{
	if (!patch.isStruct())
		throw std::runtime_error("patch root must be an object");

	const int heroId = checkedInt(requiredInteger(patch["hero"], "hero"), "hero");
	auto * hero = findHumanHero(*game.state, heroId);

	const JsonNode & statsNode = patch["stats"];
	if (!statsNode.isVector() || statsNode.Vector().size() != 4)
		throw std::runtime_error("patch field stats must contain four integers");
	std::array<si64, 4> stats{};
	for (size_t index = 0; index < stats.size(); ++index)
	{
		stats[index] = requiredInteger(statsNode[index], "stats[" + std::to_string(index) + "]");
		if (stats[index] < 0 || stats[index] > 999)
			throw std::runtime_error("stats values must be between 0 and 999");
	}

	const si64 manaValue = requiredInteger(patch["mana"], "mana");
	if (manaValue < 0 || manaValue > std::numeric_limits<si32>::max())
		throw std::runtime_error("mana is out of range");

	const bool allSpells = optionalBoolean(patch["allSpells"], "allSpells", false);
	const bool clearCheated = optionalBoolean(patch["clearCheated"], "clearCheated", false);
	bool hasSkills = false;
	std::vector<SkillEdit> skills;
	if (const auto skillsField = patch.Struct().find("skills"); skillsField != patch.Struct().end())
	{
		hasSkills = true;
		skills = parseSkills(skillsField->second);
	}
	const std::vector<ArmyEdit> army = parseArmy(patch["army"]);

	for (size_t index = 0; index < stats.size(); ++index)
		game.handler->changePrimSkill(hero, PrimarySkill(static_cast<int>(index)), stats[index], ChangeValueMode::ABSOLUTE);
	game.handler->setManaPoints(hero->id, static_cast<int>(manaValue));
	applyArmy(*game.state, hero, army);
	if (hasSkills)
		applySkills(hero, skills);
	if (allSpells)
		applyAllSpells(*game.handler, hero);
	if (clearCheated)
		game.state->players.at(hero->getOwner()).cheated = false;
}

boost::filesystem::path temporaryOutputPath(const boost::filesystem::path & output)
{
	for (int attempt = 0; attempt < 100; ++attempt)
	{
		const auto candidate = output.parent_path()
			/ (output.filename().string() + ".tmp-" + std::to_string(attempt));
		if (!boost::filesystem::exists(candidate))
			return candidate;
	}
	throw std::runtime_error("cannot allocate a temporary output path");
}

void saveAndVerify(const LoadedGame & game, const boost::filesystem::path & input, const boost::filesystem::path & output)
{
	requireNewOutput(input, output);
	const auto temporary = temporaryOutputPath(output);
	try
	{
		CSaveFile save;
		game.state->saveGame(save);
		save.save(*game.handler);
		save.write(temporary);

		// Re-open the temporary file through the complete load path before the
		// final rename, so a malformed save never becomes the user's output.
		auto verification = loadGame(temporary);
		requireEditableGame(*verification->state);
		boost::filesystem::rename(temporary, output);
	}
	catch (...)
	{
		if (boost::filesystem::exists(temporary))
			boost::filesystem::remove(temporary);
		throw;
	}
}

JsonNode successResult(const std::string & message)
{
	JsonNode result;
	result["ok"].Bool() = true;
	result["message"].String() = message;
	return result;
}

int run(int argc, char ** argv)
{
	if (argc < 3)
		throw std::runtime_error("usage: editor-engine inspect INPUT | roundtrip INPUT OUTPUT | apply INPUT OUTPUT PATCH_PATH");

	const std::string command(argv[1]);
	const boost::filesystem::path input(argv[2]);
	if (command == "inspect")
	{
		if (argc != 3)
			throw std::runtime_error("inspect expects exactly one input path");
		auto game = loadGame(input);
		std::cout << inspectGame(*game->state).toCompactString() << '\n';
		return 0;
	}

	if (command == "roundtrip")
	{
		if (argc != 4)
			throw std::runtime_error("roundtrip expects INPUT and OUTPUT");
		const boost::filesystem::path output(argv[3]);
		auto game = loadGame(input);
		requireEditableGame(*game->state);
		saveAndVerify(*game, input, output);
		std::cout << successResult("roundtrip saved").toCompactString() << '\n';
		return 0;
	}

	if (command == "apply")
	{
		if (argc != 5)
			throw std::runtime_error("apply expects INPUT, OUTPUT and PATCH_PATH");
		const boost::filesystem::path output(argv[3]);
		const boost::filesystem::path patchPath(argv[4]);
		requireInputFile(patchPath);
		auto game = loadGame(input);
		requireEditableGame(*game->state);
		applyPatch(*game, readJsonFile(patchPath));
		saveAndVerify(*game, input, output);
		std::cout << successResult("save edited").toCompactString() << '\n';
		return 0;
	}

	throw std::runtime_error("unknown command: " + command);
}

} // namespace

int main(int argc, char ** argv)
{
	try
	{
		initializeLibrary();
		const int result = run(argc, argv);
		shutdownLibrary();
		return result;
	}
	catch (const ModIncompatibility & error)
	{
		// Extract the detail before tearing down LIBRARY: getFullErrorMsg()
		// translates through the library and cannot be called afterwards.
		std::string detail(error.what());
		if (!error.whatMissing().empty())
			detail += "\nmissing mods:\n" + error.whatMissing();
		if (!error.whatExcessive().empty())
			detail += "\nexcessive mods:\n" + error.whatExcessive();
		try
		{
			shutdownLibrary();
		}
		catch (...)
		{
		}
		std::cerr << "editor-engine: " << detail << '\n';
		return 1;
	}
	catch (const std::exception & error)
	{
		try
		{
			shutdownLibrary();
		}
		catch (...)
		{
		}
		std::cerr << "editor-engine: " << error.what() << '\n';
		return 1;
	}
}
