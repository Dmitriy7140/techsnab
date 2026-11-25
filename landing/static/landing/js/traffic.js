(() => {
    const tracker = document.currentScript;
    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!csrf || !window.crypto?.randomUUID || navigator.globalPrivacyControl || navigator.doNotTrack === '1') return;
    const endpoint = tracker.dataset.endpoint;

    function send(kind, fields) {
        const data = new URLSearchParams({csrfmiddlewaretoken: csrf.value, id: crypto.randomUUID(), kind, ...fields});
        if (!navigator.sendBeacon || !navigator.sendBeacon(endpoint, data)) {
            fetch(endpoint, {method: 'POST', body: data, keepalive: true, credentials: 'same-origin'}).catch(() => {});
        }
    }

    function click(event) {
        const link = event.target.closest('a[href], #burger');
        if (!link || (event.type === 'auxclick' && event.button !== 1)) return;
        const section = link.closest('section,header,footer');
        const sectionId = section?.id || section?.classList[0] || '';
        const names = {top: 'Шапка', hero: 'Первый экран', products: 'Каталог', how: 'Как работаем',
            why: 'Преимущества', contact: 'Контакты', footer: 'Подвал'};
        const placement = names[sectionId] || sectionId;
        const label = (link.getAttribute('aria-label') || link.innerText || link.title || '').trim().replace(/\s+/g, ' ');
        send('click', {placement, label, target: link.getAttribute('href') || 'menu'});
    }
    send('view', {referrer: document.referrer ? new URL(document.referrer).origin : ''});
    document.addEventListener('click', click);
    document.addEventListener('auxclick', click);
    document.querySelector('form.form')?.addEventListener('submit', () => {
        send('click', {placement: 'Контакты', label: 'Отправить заявку', target: 'request-form'});
    });
})();
