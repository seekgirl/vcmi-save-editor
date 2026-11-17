# 二维码小工具

免费单功能工具站：纯前端二维码生成器，6 个页面，托管在 GitHub Pages。

- 首页：通用二维码生成器
- 网址转二维码 / 微信二维码 / 名片二维码（vCard）/ WiFi 二维码 / 二维码加 logo

所有二维码均在访问者浏览器本地生成，不上传、不保存任何输入内容。
二维码编码使用开源库 [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)（MIT，已本地打包在 `assets/qrcode.min.js`）。

访问量统计使用无 Cookie 的 visitorbadge.io 计数图（仅计访问次数，不收集个人信息）。

部署：本站放在 seekgirl/vcmi-save-editor 仓库的 `gh-pages` 分支（因 GitHub App 令牌无法新建仓库，暂借该仓库的分支托管；`main` 分支的项目代码不受影响）。推送到 `gh-pages` 后，GitHub Pages 自动发布到 https://seekgirl.github.io/vcmi-save-editor/ 。
