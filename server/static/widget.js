/* Drop-in loader for athanmarketing.com:
   <div id="core-audit"></div>
   <script src="https://audit.athanmarketing.com/widget.js" async></script> */
(function () {
  var me = document.currentScript || document.querySelector('script[src*="widget.js"]');
  var base = new URL(me.src).origin;
  var host = document.getElementById('core-audit');
  if (!host) { host = document.createElement('div'); me.parentNode.insertBefore(host, me); }
  var f = document.createElement('iframe');
  f.src = base + '/embed';
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
