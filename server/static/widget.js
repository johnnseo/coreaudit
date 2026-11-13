/* Drop-in loader for athanmarketing.com:
   <div id="core-audit"></div>
   <script src="https://audit.athanmarketing.com/widget.js" async></script>
   data-magnet on the div: audit (default, version 1), v2, scorecard, or ab (splits visitors between version 1 and 2). Add ?src=name to the page link to track where visitors came from. */
(function () {
  var me = document.currentScript || document.querySelector('script[src*="widget.js"]');
  var base = new URL(me.src).origin;
  var host = document.getElementById('core-audit');
  if (!host) { host = document.createElement('div'); me.parentNode.insertBefore(host, me); }
  var f = document.createElement('iframe');
  var magnet = host.getAttribute('data-magnet') || me.getAttribute('data-magnet') || 'audit';
  var src = new URLSearchParams(location.search).get('src');   // lets you tag links, e.g. ?src=youtube
  f.src = base + ({scorecard: '/scorecard', v2: '/v2', ab: '/get'}[magnet] || '/embed') + (src ? '?src=' + encodeURIComponent(src) : '');
  f.title = 'C.O.R.E. website check';
  f.loading = 'lazy';
  f.style.cssText = 'width:100%;border:0;min-height:720px;display:block;background:transparent';
  f.setAttribute('scrolling', 'no');
  host.appendChild(f);
  window.addEventListener('message', function (e) {
    if (e.origin !== base || !e.data || e.data.type !== 'core-audit-height') return;
    f.style.height = Math.max(400, e.data.height + 8) + 'px';
  });
})();
