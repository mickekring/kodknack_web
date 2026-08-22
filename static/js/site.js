/* The site works fully without this file. It only adds two conveniences. */
(function () {
  'use strict';

  // Close an open nav dropdown when focus or a click goes elsewhere.
  var groups = Array.prototype.slice.call(document.querySelectorAll('.nav-grupp'));
  function closeOthers(keep) {
    groups.forEach(function (g) { if (g !== keep) { g.open = false; } });
  }
  groups.forEach(function (g) {
    g.addEventListener('toggle', function () { if (g.open) { closeOthers(g); } });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.nav-grupp')) { closeOthers(null); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeOthers(null); }
  });

  // Load a third-party embed only once the visitor asks for it.
  document.querySelectorAll('.extern .extern-knapp').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var figure = btn.closest('.extern');
      var frame = document.createElement('iframe');
      frame.src = figure.dataset.inbaddning;
      frame.title = figure.dataset.titel;
      frame.loading = 'lazy';
      frame.allowFullscreen = true;
      frame.referrerPolicy = 'no-referrer';
      figure.replaceChildren(frame);
    });
  });
})();
