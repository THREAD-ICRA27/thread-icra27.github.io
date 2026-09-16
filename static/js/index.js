// THREAD project page: clips play while on screen, clips with data-fps get a
// frame scrubber, optional episode selectors swap clips, and the BibTeX block
// copies. No external dependencies. Each feature is isolated in try/catch so a
// malformed card cannot stop the rest of the page from working.
(function () {
  function frameOf(v) {
    var fps = parseFloat(v.dataset.fps) || 1, n = parseInt(v.dataset.frames, 10) || 1;
    return Math.max(0, Math.min(n - 1, Math.floor(v.currentTime * fps + 1e-4)));
  }
  function seekTo(v, k) {
    var fps = parseFloat(v.dataset.fps) || 1, n = parseInt(v.dataset.frames, 10) || 1;
    k = ((k % n) + n) % n;
    v.currentTime = (k + 0.5) / fps;  // the middle of frame k
  }
  function safePlay(v) { var p = v.play(); if (p && p.catch) { p.catch(function () {}); } }

  // The scrubber fills a pre-authored <div class="scrub"> right after the video
  // (the slot has a fixed min-height, so the page does not reflow when this runs).
  function attachScrubber(v) {
    if (v.dataset.scrub) { return; }
    v.dataset.scrub = '1';
    var box = v.nextElementSibling;
    if (!box || !box.classList.contains('scrub')) {
      box = document.createElement('div'); box.className = 'scrub';
      v.parentNode.insertBefore(box, v.nextSibling);
    }
    box.textContent = '';
    box.removeAttribute('aria-hidden');
    var card = v.closest ? v.closest('.card') : null;
    var titleEl = card && card.querySelector('.card-title');
    var label = titleEl ? titleEl.textContent.trim() : 'clip';
    var play = document.createElement('button'); play.type = 'button'; play.className = 'scrub-play'; play.title = 'Play or pause'; play.textContent = 'Pause';
    var prev = document.createElement('button'); prev.type = 'button'; prev.title = 'Previous frame'; prev.setAttribute('aria-label', 'Previous frame'); prev.textContent = '◀';
    var next = document.createElement('button'); next.type = 'button'; next.title = 'Next frame'; next.setAttribute('aria-label', 'Next frame'); next.textContent = '▶';
    var range = document.createElement('input'); range.type = 'range'; range.min = 0; range.step = 1;
    range.setAttribute('aria-label', 'Frame of ' + label);
    var out = document.createElement('span'); out.className = 'scrub-readout'; out.title = 'frame';
    var fs = document.createElement('button'); fs.type = 'button'; fs.className = 'scrub-fs'; fs.title = 'Full screen'; fs.setAttribute('aria-label', 'Full screen'); fs.textContent = '\u2922';
    fs.addEventListener('click', function () {
      var req = v.requestFullscreen || v.webkitRequestFullscreen || v.msRequestFullscreen;
      if (req) { var r = req.call(v); if (r && r.catch) { r.catch(function () {}); } }
      else if (v.webkitEnterFullscreen) { v.webkitEnterFullscreen(); }  // iOS Safari
    });
    function n() { return parseInt(v.dataset.frames, 10) || 1; }
    function refresh() {
      var k = frameOf(v); range.max = n() - 1; range.value = k;
      out.textContent = k + ' / ' + (n() - 1);
      play.textContent = v.paused ? 'Play' : 'Pause';
    }
    function userPause() { v.pause(); v.dataset.userPaused = '1'; }
    play.addEventListener('click', function () {
      if (v.paused) { v.dataset.userPaused = ''; safePlay(v); } else { userPause(); }
      refresh();
    });
    prev.addEventListener('click', function () { userPause(); seekTo(v, frameOf(v) - 1); });
    next.addEventListener('click', function () { userPause(); seekTo(v, frameOf(v) + 1); });
    range.addEventListener('input', function () { userPause(); seekTo(v, parseInt(range.value, 10)); });
    ['timeupdate', 'seeked', 'play', 'pause', 'loadedmetadata'].forEach(function (e) { v.addEventListener(e, refresh); });
    box.appendChild(play); box.appendChild(prev); box.appendChild(next); box.appendChild(range); box.appendChild(out); box.appendChild(fs);
    refresh();
  }
  document.querySelectorAll('video[data-fps]').forEach(function (v) {
    try { attachScrubber(v); } catch (e) { /* leave this clip without a scrubber */ }
  });

  // play while on screen, unless the viewer paused it or prefers reduced motion
  try {
    var lazy = document.querySelectorAll('video[data-autoplay]');
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if ('IntersectionObserver' in window && lazy.length) {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          var v = e.target;
          // with reduced motion nothing starts on its own, but clips still pause when scrolled away
          if (e.isIntersecting) { if (!reduced && v.dataset.userPaused !== '1') { safePlay(v); } }
          else { v.pause(); }
        });
      }, { threshold: 0.35 });
      lazy.forEach(function (v) { obs.observe(v); });
    }
  } catch (e) {}

  // Optional episode selector (not used on the page yet): buttons inside
  // <div class="ep-select"> swap the first video of the same card. Each button
  // carries data-src, data-poster and, for the scrubber, data-fps/data-frames.
  // Give every clip in one card the same pixel size so the card never reflows.
  document.querySelectorAll('.ep-select').forEach(function (sel) {
    try {
      var video = sel.parentElement.querySelector('video');
      var source = video && video.querySelector('source');
      if (!video || !source) { return; }
      sel.querySelectorAll('.ep-btn').forEach(function (b) {
        b.addEventListener('click', function () {
          if (b.disabled || b.classList.contains('is-active')) { return; }
          sel.querySelectorAll('.ep-btn').forEach(function (x) { x.classList.remove('is-active'); });
          b.classList.add('is-active');
          video.setAttribute('poster', b.getAttribute('data-poster'));
          source.setAttribute('src', b.getAttribute('data-src'));
          if (b.getAttribute('data-fps')) { video.dataset.fps = b.getAttribute('data-fps'); video.dataset.frames = b.getAttribute('data-frames'); }
          video.dataset.userPaused = '';
          video.load();
          safePlay(video);
        });
      });
    } catch (e) {}
  });

  try {
    var btn = document.getElementById('copy-bibtex');
    var code = document.getElementById('bibtex-code');
    if (btn && code) {
      btn.addEventListener('click', function () {
        var text = code.textContent;
        var show = function (msg) { btn.textContent = msg; setTimeout(function () { btn.textContent = 'Copy'; }, 1500); };
        var fallback = function () {
          var ok = false, ta = document.createElement('textarea');
          ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
          document.body.appendChild(ta); ta.select();
          try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
          document.body.removeChild(ta);
          if (ok) { show('Copied'); }
          else {  // leave the entry selected so the reader can copy it by hand
            var r = document.createRange(); r.selectNodeContents(code);
            var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
            show('Press Ctrl+C');
          }
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () { show('Copied'); }, fallback);
        } else { fallback(); }
      });
    }
  } catch (e) {}
})();
