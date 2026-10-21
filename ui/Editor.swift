// SPDX-FileCopyrightText: 2026 seekgirl
// SPDX-License-Identifier: GPL-3.0-or-later

import AppKit
import Darwin
import Foundation
import SwiftUI

private struct SaveDocument: Codable, Sendable {
    let version: Int
    let day: Int
    let heroes: [Hero]
    let creatures: [Creature]
    let skills: [SkillDefinition]
}

private struct Hero: Codable, Identifiable, Sendable {
    let id: Int
    let name: String
    let owner: Int
    let attack: Int
    let defense: Int
    let power: Int
    let knowledge: Int
    let mana: Int
    let cheated: Bool
    let human: Bool?
    let army: [ArmySlot]
    let skills: [LearnedSkill]
}

private struct Creature: Codable, Identifiable, Sendable {
    let id: Int
    let name: String
}

private struct SkillDefinition: Codable, Identifiable, Sendable {
    let id: Int
    let name: String
}

private struct LearnedSkill: Codable, Identifiable, Sendable {
    var id: Int
    var level: Int
}

private struct ArmySlot: Codable, Identifiable, Sendable {
    var slot: Int
    var creature: Int
    var count: Int

    var id: Int { slot }
}

private struct SavePatch: Encodable, Sendable {
    let hero: Int
    let stats: [Int]
    let mana: Int
    let allSpells: Bool
    let clearCheated: Bool
    let army: [ArmySlot]
    let skills: [LearnedSkill]
}

private struct ApplyResponse: Decodable, Sendable {
    let ok: Bool
    let message: String?
    let error: String?

    var detail: String {
        message ?? error ?? (ok ? "操作完成" : "引擎未接受修改")
    }
}

private enum TaskOutcome<Value: Sendable>: Sendable {
    case success(Value)
    case failure(String)
}

private enum BackendError: Error, LocalizedError, Sendable {
    case unavailable(String)
    case commandFailed(Int32, String)
    case invalidJSON
    case outputMissing
    case inputChanged
    case replacementFailed(String)
    case timeout

    var errorDescription: String? {
        switch self {
        case .unavailable(let message):
            return message
        case .commandFailed(let status, let detail):
            return "引擎执行失败（\(status)）：\(detail)"
        case .invalidJSON:
            return "引擎没有返回可识别的 JSON 结果"
        case .outputMissing:
            return "引擎返回成功，但没有找到候选存档"
        case .inputChanged:
            return "原存档已被游戏更新，请重新读取最新存档"
        case .replacementFailed(let detail):
            return "覆盖保存失败：\(detail)"
        case .timeout:
            return "引擎执行超过 120 秒，已终止操作"
        }
    }
}

private enum EditorBackend {
    private static let expectedVCMIVersion = "1.7.5"
    private static let expectedVCMICommit = "6901839ae9760dfcd1d5ff2c4aa4ef6968fee752"

    static func inspect(at input: URL) throws -> SaveDocument {
        let stdout = try run(arguments: ["inspect", input.path])
        return try decodeLastJSON(SaveDocument.self, from: stdout)
    }

    static func apply(patch: SavePatch, input: URL, output: URL) throws -> ApplyResponse {
        let patchURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("vcmi-editor-\(UUID().uuidString).json")
        defer { try? FileManager.default.removeItem(at: patchURL) }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        try encoder.encode(patch).write(to: patchURL, options: .atomic)

        let stdout = try run(arguments: ["apply", input.path, output.path, patchURL.path])
        let response = try decodeLastJSON(ApplyResponse.self, from: stdout)
        guard response.ok else {
            throw BackendError.commandFailed(0, response.detail)
        }
        guard FileManager.default.fileExists(atPath: output.path) else {
            throw BackendError.outputMissing
        }
        return response
    }

    static func overwrite(patch: SavePatch, input: URL) throws -> ApplyResponse {
        let target = input.standardizedFileURL.resolvingSymlinksInPath()
        let fileManager = FileManager.default
        let originalData = try Data(contentsOf: target)
        let originalAttributes = try? fileManager.attributesOfItem(atPath: target.path)
        let candidate = target.deletingLastPathComponent()
            .appendingPathComponent(".vcmi-edit-\(UUID().uuidString).vsgm1")
        defer { try? fileManager.removeItem(at: candidate) }

        let response = try apply(patch: patch, input: target, output: candidate)
        let currentData = try Data(contentsOf: target)
        guard currentData == originalData else {
            throw BackendError.inputChanged
        }

        if let permissions = originalAttributes?[.posixPermissions] as? NSNumber {
            try? fileManager.setAttributes([.posixPermissions: permissions], ofItemAtPath: candidate.path)
        }

        let renameStatus = candidate.path.withCString { candidatePath in
            target.path.withCString { targetPath in
                Darwin.rename(candidatePath, targetPath)
            }
        }
        guard renameStatus == 0 else {
            let detail = String(cString: strerror(errno))
            throw BackendError.replacementFailed(detail)
        }
        return response
    }

    private static func run(arguments: [String]) throws -> String {
        guard let resourceURL = Bundle.main.resourceURL else {
            throw BackendError.unavailable("无法找到应用资源目录")
        }

        let vcmiAppURL = try configuredVCMIApp()

        let executableURL = resourceURL.appendingPathComponent("editor-engine")
        guard FileManager.default.isExecutableFile(atPath: executableURL.path) else {
            throw BackendError.unavailable("未找到可执行的 editor-engine")
        }

        let process = Process()
        process.executableURL = executableURL
        process.arguments = arguments

        // The helper loads VCMI from the selected installation. Remove every
        // inherited DYLD_* value first so a shell or launcher cannot redirect
        // it to an unrelated library tree.
        var environment = ProcessInfo.processInfo.environment
        for key in environment.keys.filter({ $0.hasPrefix("DYLD_") }) {
            environment.removeValue(forKey: key)
        }
        environment["VCMI_APP_PATH"] = vcmiAppURL.path
        environment["DYLD_LIBRARY_PATH"] = vcmiAppURL
            .appendingPathComponent("Contents/Frameworks", isDirectory: true)
            .path
        process.environment = environment

        let fileManager = FileManager.default
        let logDirectory = fileManager.temporaryDirectory
            .appendingPathComponent("vcmi-editor-\(UUID().uuidString)", isDirectory: true)
        try fileManager.createDirectory(at: logDirectory, withIntermediateDirectories: true)
        defer { try? fileManager.removeItem(at: logDirectory) }

        let stdoutURL = logDirectory.appendingPathComponent("stdout.log")
        let stderrURL = logDirectory.appendingPathComponent("stderr.log")
        guard fileManager.createFile(atPath: stdoutURL.path, contents: nil),
              fileManager.createFile(atPath: stderrURL.path, contents: nil) else {
            throw BackendError.unavailable("无法创建引擎日志临时文件")
        }

        let stdoutHandle = try FileHandle(forWritingTo: stdoutURL)
        let stderrHandle = try FileHandle(forWritingTo: stderrURL)
        process.standardOutput = stdoutHandle
        process.standardError = stderrHandle

        do {
            try process.run()
        } catch {
            stdoutHandle.closeFile()
            stderrHandle.closeFile()
            throw error
        }

        let deadline = Date().addingTimeInterval(120)
        while process.isRunning && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.05)
        }

        var timedOut = false
        if process.isRunning {
            timedOut = true
            process.terminate()

            let terminateDeadline = Date().addingTimeInterval(1)
            while process.isRunning && Date() < terminateDeadline {
                Thread.sleep(forTimeInterval: 0.05)
            }
            if process.isRunning {
                _ = Darwin.kill(process.processIdentifier, SIGKILL)
            }
        }

        process.waitUntilExit()
        stdoutHandle.closeFile()
        stderrHandle.closeFile()

        if timedOut {
            throw BackendError.timeout
        }

        let stdout = String(data: try Data(contentsOf: stdoutURL), encoding: .utf8) ?? ""
        let stderr = String(data: try Data(contentsOf: stderrURL), encoding: .utf8) ?? ""

        guard process.terminationStatus == 0 else {
            let detail = (stderr.isEmpty ? stdout : stderr)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            throw BackendError.commandFailed(process.terminationStatus, detail.isEmpty ? "无错误详情" : detail)
        }
        return stdout
    }

    private static func configuredVCMIApp() throws -> URL {
        let configuredPath = (ProcessInfo.processInfo.environment["VCMI_APP_PATH"]
            ?? Bundle.main.object(forInfoDictionaryKey: "VCMIAppPath") as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let path = configuredPath?.isEmpty == false ? configuredPath! : "/Applications/VCMI.app"
        let appURL = URL(fileURLWithPath: path).standardizedFileURL
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: appURL.path),
              (try? appURL.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true else {
            throw BackendError.unavailable(
                "未找到 VCMI 安装：\(appURL.path)。请检查应用 Info.plist 的 VCMIAppPath。"
            )
        }

        let infoURL = appURL.appendingPathComponent("Contents/Info.plist")
        guard let infoData = try? Data(contentsOf: infoURL),
              let propertyList = try? PropertyListSerialization.propertyList(
                  from: infoData,
                  options: [],
                  format: nil
              ),
              let info = propertyList as? [String: Any] else {
            throw BackendError.unavailable("无法读取 VCMI 安装信息：\(infoURL.path)")
        }

        let version = info["CFBundleShortVersionString"] as? String ?? "未知"
        let commit = info["CFBundleVersion"] as? String ?? "未知"
        guard version == expectedVCMIVersion, commit == expectedVCMICommit else {
            throw BackendError.unavailable(
                "VCMI 版本不匹配：需要 \(expectedVCMIVersion) / \(expectedVCMICommit)，" +
                    "实际为 \(version) / \(commit)。"
            )
        }

        let frameworksURL = appURL.appendingPathComponent("Contents/Frameworks", isDirectory: true)
        guard fileManager.fileExists(atPath: frameworksURL.path),
              (try? frameworksURL.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true else {
            throw BackendError.unavailable("VCMI Frameworks 目录不存在：\(frameworksURL.path)")
        }
        return appURL
    }

    private static func decodeLastJSON<T: Decodable>(_ type: T.Type, from output: String) throws -> T {
        if let value = try? JSONDecoder().decode(T.self, from: Data(output.utf8)) {
            return value
        }
        for line in output.split(whereSeparator: \.isNewline).reversed() {
            if let value = try? JSONDecoder().decode(T.self, from: Data(line.utf8)) {
                return value
            }
        }
        throw BackendError.invalidJSON
    }
}

private struct IntegerField: View {
    let title: String
    @Binding var value: Int

    var body: some View {
        TextField(title, text: Binding(
            get: { String(value) },
            set: { value = Int($0) ?? 0 }
        ))
        .textFieldStyle(.roundedBorder)
    }
}

private enum SaveLocator {
    private static let resourceKeys: Set<URLResourceKey> = [
        .isDirectoryKey,
        .isHiddenKey,
        .isPackageKey,
        .isRegularFileKey,
        .contentModificationDateKey
    ]

    static func latestSave(in directory: URL) -> URL? {
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: directory.path),
              let values = try? directory.resourceValues(forKeys: [.isDirectoryKey]),
              values.isDirectory == true,
              let enumerator = fileManager.enumerator(
                at: directory,
                includingPropertiesForKeys: Array(resourceKeys),
                options: [.skipsHiddenFiles, .skipsPackageDescendants],
                errorHandler: { _, _ in true }
              ) else {
            return nil
        }

        var latestURL: URL?
        var latestDate = Date.distantPast

        for case let url as URL in enumerator {
            guard let values = try? url.resourceValues(forKeys: resourceKeys) else {
                continue
            }

            if values.isDirectory == true {
                if isTemporaryDirectory(url.lastPathComponent) {
                    enumerator.skipDescendants()
                }
                continue
            }

            guard values.isPackage != true,
                  values.isRegularFile == true,
                  url.pathExtension.lowercased() == "vsgm1",
                  let modificationDate = values.contentModificationDate,
                  !isTemporaryFile(url.lastPathComponent) else {
                continue
            }

            if modificationDate > latestDate {
                latestDate = modificationDate
                latestURL = url
            }
        }

        return latestURL
    }

    private static func isTemporaryDirectory(_ name: String) -> Bool {
        let lowercased = name.lowercased()
        return lowercased == "tmp"
            || lowercased == "temp"
            || lowercased.hasPrefix("tmp-")
            || lowercased.hasPrefix("temp-")
            || lowercased.hasSuffix(".tmp")
            || lowercased.hasSuffix(".temp")
            || lowercased.hasSuffix("~")
    }

    private static func isTemporaryFile(_ name: String) -> Bool {
        let lowercased = name.lowercased()
        return lowercased.hasPrefix(".~")
            || lowercased.hasPrefix("~")
            || lowercased.hasSuffix(".tmp")
            || lowercased.hasSuffix(".temp")
            || lowercased.hasSuffix("~")
    }
}

@MainActor
private struct EditorView: View {
    @State private var document: SaveDocument?
    @State private var loadedURL: URL?
    @State private var selectedHeroID: Int = 0
    @State private var statusText = "读取最新存档后修改，点击保存直接覆盖当前存档"
    @State private var isBusy = false

    @State private var attack = 1
    @State private var defense = 1
    @State private var power = 1
    @State private var knowledge = 1
    @State private var mana = 0
    @State private var allSpells = false
    @State private var preserveCheated = false
    @State private var army = (0..<7).map { ArmySlot(slot: $0, creature: 0, count: 0) }
    @State private var learnedSkills: [LearnedSkill] = []
    @State private var skillToAddId: Int?

    private var defaultSavesDirectory: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/vcmi/Saves", isDirectory: true)
    }

    private var heroes: [Hero] { (document?.heroes ?? []).filter { $0.human != false } }
    private var creatures: [Creature] { document?.creatures ?? [] }
    private var skillCatalog: [SkillDefinition] { document?.skills ?? [] }
    private var learnedSkillIDs: Set<Int> { Set(learnedSkills.map(\.id)) }
    private var availableSkillsToAdd: [SkillDefinition] {
        skillCatalog.filter { !learnedSkillIDs.contains($0.id) }
    }
    private var selectedHero: Hero? {
        heroes.first(where: { $0.id == selectedHeroID })
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            toolbar
            Divider()

            if document == nil {
                emptyState
            } else {
                editorContent
            }

            Divider()
            footer
        }
        .frame(minWidth: 760, minHeight: 700)
    }

    private var toolbar: some View {
        HStack(spacing: 12) {
            Button("打开 .vsgm1 存档") { openSave() }
                .disabled(isBusy)

            Button("打开最新存档") { openLatestSave() }
                .buttonStyle(.borderedProminent)
                .disabled(isBusy)

            if !heroes.isEmpty {
                Picker("英雄", selection: Binding(
                    get: { selectedHeroID },
                    set: { id in
                        selectedHeroID = id
                        if let hero = heroes.first(where: { $0.id == id }) {
                            loadHero(hero)
                        }
                    }
                )) {
                    ForEach(heroes) { hero in
                        Text(heroDisplayName(hero)).tag(hero.id)
                    }
                }
                .frame(width: 250)
                .disabled(isBusy)
            }

            Spacer()

            if isBusy {
                ProgressView()
                    .controlSize(.small)
                Text("处理中…")
                    .foregroundColor(.secondary)
            }
        }
        .padding(16)
    }

    private var editorContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                heroSummary
                statsSection
                skillsSection
                armySection
                optionsSection
            }
            .padding(20)
        }
    }

    private var heroSummary: some View {
        GroupBox("当前英雄") {
            HStack(spacing: 22) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(selectedHero.map(heroDisplayName) ?? "未选择英雄")
                        .font(.title3)
                    if let hero = selectedHero {
                        Text("英雄 ID \(hero.id) · 所属玩家 \(hero.owner) · 原始作弊标记：\(hero.cheated ? "已标记" : "未标记")")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                if let url = loadedURL {
                    Text(url.lastPathComponent)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
            .padding(4)
        }
    }

    private var statsSection: some View {
        GroupBox("基础四维与魔法值") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 12) {
                    labeledInteger("攻击", value: $attack)
                    labeledInteger("防御", value: $defense)
                    labeledInteger("力量", value: $power)
                    labeledInteger("知识", value: $knowledge)
                    labeledInteger("魔法值", value: $mana)
                }
                Text("这里修改的是基础四维，装备加成另计。")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(4)
        }
    }

    private var skillsSection: some View {
        GroupBox("已学习的技能") {
            VStack(alignment: .leading, spacing: 10) {
                if learnedSkills.isEmpty {
                    Text("暂无已学习技能")
                        .foregroundColor(.secondary)
                } else {
                    ForEach($learnedSkills) { $skill in
                        HStack(spacing: 10) {
                            Text(skillDisplayName(skill.id))
                                .frame(maxWidth: .infinity, alignment: .leading)

                            Picker("等级", selection: $skill.level) {
                                Text("初级").tag(1)
                                Text("中级").tag(2)
                                Text("高级").tag(3)
                            }
                            .labelsHidden()
                            .pickerStyle(.menu)
                            .frame(width: 100, alignment: .leading)

                            Button("移除") {
                                removeSkill(id: skill.id)
                            }
                            .buttonStyle(.borderless)
                        }
                    }
                }

                Divider()

                HStack(spacing: 10) {
                    Picker("添加技能", selection: $skillToAddId) {
                        if availableSkillsToAdd.isEmpty {
                            Text("暂无可添加技能").tag(nil as Int?)
                        } else {
                            ForEach(availableSkillsToAdd) { skill in
                                Text(skillDisplayName(skill))
                                    .tag(skill.id as Int?)
                            }
                        }
                    }
                    .labelsHidden()
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)

                    Button("添加") { addSkill() }
                        .disabled(skillToAddId == nil || availableSkillsToAdd.isEmpty)
                }

                Text("技能等级可选初级、中级或高级。")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(4)
        }
        .disabled(isBusy)
    }

    private var armySection: some View {
        GroupBox("部队（7 个兵槽）") {
            VStack(spacing: 8) {
                HStack {
                    Text("槽位").frame(width: 52, alignment: .leading)
                    Text("兵种 ID").frame(width: 130, alignment: .leading)
                    Text("兵种名称").frame(maxWidth: .infinity, alignment: .leading)
                    Text("数量").frame(width: 130, alignment: .leading)
                }
                .font(.caption)
                .foregroundColor(.secondary)

                ForEach(0..<7, id: \.self) { index in
                    HStack(spacing: 10) {
                        Text("\(index + 1)")
                            .frame(width: 52, alignment: .leading)
                        IntegerField(title: "兵种 ID", value: Binding(
                            get: { army[index].creature },
                            set: { army[index].creature = $0 }
                        ))
                        .frame(width: 130)
                        Picker("兵种名称", selection: Binding(
                            get: { army[index].creature },
                            set: { army[index].creature = $0 }
                        )) {
                            Text("空").tag(0)
                            ForEach(creatureOptions(for: army[index].creature)) { creature in
                                Text("\(creatureDisplayName(creature))（ID \(creature.id)）")
                                    .tag(creature.id)
                            }
                        }
                        .labelsHidden()
                        .pickerStyle(.menu)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        IntegerField(title: "数量", value: Binding(
                            get: { army[index].count },
                            set: { army[index].count = $0 }
                        ))
                        .frame(width: 130)
                    }
                }
            }
            .padding(4)
        }
    }

    private var optionsSection: some View {
        GroupBox("其他修改") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("赋予全部魔法", isOn: $allSpells)
                Toggle("清除作弊者标记", isOn: Binding(get: { !preserveCheated }, set: { preserveCheated = !$0 }))
                Text("默认勾选。勾选时清除该玩家已有的作弊标记；取消勾选则保留原状态。")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(4)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Spacer()
            Text("打开一个单机 .vsgm1 存档开始编辑")
                .font(.title3)
            Text("读取最新存档后修改，点击保存直接覆盖当前存档")
                .foregroundColor(.secondary)
            Text("默认存档目录")
                .font(.caption)
                .foregroundColor(.secondary)
            Text(defaultSavesDirectory.path)
                .font(.caption.monospaced())
                .foregroundColor(.secondary)
                .textSelection(.enabled)
            Button("选择存档") { openSave() }
                .disabled(isBusy)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var footer: some View {
        HStack(alignment: .center, spacing: 12) {
            Text(statusText)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(2)
                .truncationMode(.tail)

            Spacer()

            Button("保存") { save() }
                .keyboardShortcut("s", modifiers: [.command])
                .disabled(document == nil || loadedURL == nil || selectedHero == nil || isBusy)

            Button("关闭") { NSApplication.shared.terminate(nil) }
                .disabled(isBusy)
        }
        .padding(16)
    }

    private func labeledInteger(_ label: String, value: Binding<Int>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            IntegerField(title: label, value: value)
                .frame(width: 100)
        }
    }

    private func heroDisplayName(_ hero: Hero) -> String {
        hero.name.isEmpty ? "英雄 \(hero.id)" : "\(hero.name)（ID \(hero.id)）"
    }

    private func creatureOptions(for currentID: Int) -> [Creature] {
        guard currentID != 0,
              !creatures.contains(where: { $0.id == currentID }) else {
            return creatures
        }
        let current = Creature(id: currentID, name: "当前兵种 \(currentID)")
        return [current] + creatures
    }

    private func creatureDisplayName(_ creature: Creature) -> String {
        creature.name.isEmpty ? "兵种 \(creature.id)" : creature.name
    }

    private func loadHero(_ hero: Hero) {
        attack = hero.attack
        defense = hero.defense
        power = hero.power
        knowledge = hero.knowledge
        mana = hero.mana
        preserveCheated = false
        army = normalisedArmy(hero.army)
        learnedSkills = hero.skills
        syncSkillToAddSelection()
        allSpells = false
    }

    private func skillDisplayName(_ skill: SkillDefinition) -> String {
        skill.name.isEmpty ? "技能 ID \(skill.id)" : skill.name
    }

    private func skillDisplayName(_ id: Int) -> String {
        guard let skill = skillCatalog.first(where: { $0.id == id }) else {
            return "技能 ID \(id)"
        }
        return skillDisplayName(skill)
    }

    private func syncSkillToAddSelection() {
        skillToAddId = skillCatalog.first(where: { !learnedSkillIDs.contains($0.id) })?.id
    }

    private func addSkill() {
        guard let id = skillToAddId,
              skillCatalog.contains(where: { $0.id == id }),
              !learnedSkillIDs.contains(id) else {
            return
        }

        learnedSkills.append(LearnedSkill(id: id, level: 1))
        syncSkillToAddSelection()
    }

    private func removeSkill(id: Int) {
        learnedSkills.removeAll { $0.id == id }
        syncSkillToAddSelection()
    }

    private func normalisedArmy(_ source: [ArmySlot]) -> [ArmySlot] {
        var result = (0..<7).map { ArmySlot(slot: $0, creature: 0, count: 0) }
        for item in source where (0..<7).contains(item.slot) {
            result[item.slot] = ArmySlot(slot: item.slot, creature: item.creature, count: item.count)
        }
        return result
    }

    private func openSave() {
        let panel = NSOpenPanel()
        panel.allowedFileTypes = ["vsgm1"]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.canChooseFiles = true

        let fileManager = FileManager.default
        if let loadedURL,
           fileManager.fileExists(atPath: loadedURL.deletingLastPathComponent().path) {
            panel.directoryURL = loadedURL.deletingLastPathComponent()
        } else if fileManager.fileExists(atPath: defaultSavesDirectory.path) {
            panel.directoryURL = defaultSavesDirectory
        }

        guard panel.runModal() == .OK, let url = panel.url else { return }
        inspect(url)
    }

    private func openLatestSave() {
        guard !isBusy else { return }

        let directory = defaultSavesDirectory
        isBusy = true
        statusText = "正在扫描默认存档目录…"

        let task = Task.detached(priority: .userInitiated) {
            SaveLocator.latestSave(in: directory)
        }

        Task { @MainActor in
            let latestURL = await task.value
            isBusy = false

            if let latestURL {
                inspect(latestURL)
            } else {
                statusText = "默认目录中没有找到 .vsgm1 存档，请使用“打开 .vsgm1 存档”手动选择。"
            }
        }
    }

    private func inspect(_ url: URL) {
        guard !isBusy else { return }
        guard url.pathExtension.lowercased() == "vsgm1" else {
            statusText = "请选择 .vsgm1 存档"
            return
        }

        isBusy = true
        statusText = "正在读取存档…"

        let task = Task.detached(priority: .userInitiated) { () -> TaskOutcome<SaveDocument> in
            do {
                return .success(try EditorBackend.inspect(at: url))
            } catch {
                return .failure(error.localizedDescription)
            }
        }

        Task { @MainActor in
            let result = await task.value

            switch result {
            case .success(let parsed):
                document = parsed
                loadedURL = url
                if let firstHero = parsed.heroes.first(where: { $0.human != false }) {
                    selectedHeroID = firstHero.id
                    loadHero(firstHero)
                    statusText = "已读取 \(url.lastPathComponent)，修改内容后点击保存直接覆盖当前存档。"
                } else {
                    selectedHeroID = 0
                    statusText = "存档中没有可编辑的英雄。"
                }
            case .failure(let message):
                statusText = "读取失败：\(message)"
            }
            isBusy = false
        }
    }

    private func save() {
        guard let input = loadedURL, let hero = selectedHero else { return }

        let patch = SavePatch(
            hero: hero.id,
            stats: [attack, defense, power, knowledge],
            mana: mana,
            allSpells: allSpells,
            clearCheated: !preserveCheated,
            army: army,
            skills: learnedSkills
        )

        isBusy = true
        statusText = "正在覆盖保存修改后的存档…"

        let task = Task.detached(priority: .userInitiated) { () -> TaskOutcome<(ApplyResponse, SaveDocument?)> in
            do {
                let response = try EditorBackend.overwrite(patch: patch, input: input)
                do {
                    let refreshed = try EditorBackend.inspect(at: input)
                    return .success((response, refreshed))
                } catch {
                    return .success((response, nil))
                }
            } catch {
                return .failure(error.localizedDescription)
            }
        }

        Task { @MainActor in
            let result = await task.value

            switch result {
            case .success(let (response, refreshed)):
                guard let refreshed else {
                    statusText = "已保存，但界面刷新失败，请重新读取"
                    break
                }
                document = refreshed
                loadedURL = input
                if let refreshedHero = refreshed.heroes.first(where: { $0.id == selectedHeroID && $0.human != false })
                    ?? refreshed.heroes.first(where: { $0.human != false }) {
                    selectedHeroID = refreshedHero.id
                    loadHero(refreshedHero)
                    statusText = "已保存 \(input.lastPathComponent)：\(response.detail)"
                } else {
                    selectedHeroID = 0
                    statusText = "已保存 \(input.lastPathComponent)，但存档中没有可编辑的英雄。"
                }
            case .failure(let message):
                statusText = "保存失败：\(message)"
            }
            isBusy = false
        }
    }
}

@main
struct VCMISaveEditorApp: App {
    var body: some Scene {
        WindowGroup("VCMI 存档修改器") {
            EditorView()
        }
    }
}
