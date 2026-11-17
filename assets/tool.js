/* 二维码小工具 — 共享逻辑。纯前端：二维码在浏览器本地生成，不上传任何内容。 */
(function () {
  'use strict';

  // 每生成一次，向无 Cookie 计数服务发一个 1px 请求（仅计数，无个人信息）。
  // 计数键按页面区分，例如 seekgirl.github.io/gen/url。
  function countGeneration(key) {
    try {
      var img = new Image();
      img.src = 'https://api.visitorbadge.io/api/visitors?path=' +
        encodeURIComponent('seekgirl.github.io/gen/' + key) +
        '&label=%E7%94%9F%E6%88%90%E6%AC%A1%E6%95%B0&countColor=%230b6fa4';
    } catch (e) { /* 计数失败不影响生成 */ }
  }

  // 在 canvas 上绘制二维码；opts: size(像素), level(纠错等级), fg, bg, logo(Image|null)
  function drawQR(canvas, text, opts) {
    opts = opts || {};
    var level = opts.level || 'M';
    var size = opts.size || 480;
    var qr = qrcode(0, level); // 0 = 自动选择版本
    qr.addData(text);
    qr.make();
    var n = qr.getModuleCount();
    var scale = Math.max(1, Math.floor(size / n));
    var px = n * scale;
    canvas.width = px;
    canvas.height = px;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = opts.bg || '#ffffff';
    ctx.fillRect(0, 0, px, px);
    ctx.fillStyle = opts.fg || '#111111';
    for (var r = 0; r < n; r++) {
      for (var c = 0; c < n; c++) {
        if (qr.isDark(r, c)) ctx.fillRect(c * scale, r * scale, scale, scale);
      }
    }
    if (opts.logo) {
      var lw = Math.round(px * 0.22);
      var lx = Math.round((px - lw) / 2);
      ctx.fillStyle = '#ffffff';
      var pad = Math.round(lw * 0.08);
      ctx.fillRect(lx - pad, lx - pad, lw + pad * 2, lw + pad * 2);
      ctx.drawImage(opts.logo, lx, lx, lw, lw);
    }
    return { modules: n, px: px };
  }

  function downloadCanvas(canvas, filename) {
    var a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = filename || 'qrcode.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function showErr(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
  }
  function hideErr(el) { if (el) el.style.display = 'none'; }

  window.QRTool = {
    draw: drawQR,
    download: downloadCanvas,
    count: countGeneration,
    showErr: showErr,
    hideErr: hideErr
  };
})();
