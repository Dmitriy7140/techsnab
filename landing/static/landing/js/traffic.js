(() => {
    const tracker = document.currentScript;
    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const panel = document.getElementById('cookie-choice');
    if (!csrf || !panel) return;
    const privateMode = navigator.globalPrivacyControl || navigator.doNotTrack === '1' || panel.dataset.state === 'private';
    let enabled = panel.dataset.state === 'allow' && !privateMode;
    const endpoint = tracker.dataset.endpoint;
    const choiceForm = panel.querySelector('form');
    const settingsLink = document.querySelector('.cookie-settings');
    settingsLink.addEventListener('click', event => {
        event.preventDefault();
        panel.hidden = false;
        panel.querySelector('button').focus();
    });
    choiceForm.addEventListener('submit', async event => {
        if (!event.submitter) return;
        event.preventDefault();
        const data = new URLSearchParams(new FormData(choiceForm));
        data.set('choice', privateMode ? 'deny' : event.submitter.value);
        if (document.referrer) data.set('referrer', new URL(document.referrer).origin);
        const error = panel.querySelector('.cookie-error');
        const buttons = [...choiceForm.querySelectorAll('button')];
        buttons.forEach(b => { b.disabled = true; });
        try {
            const result = await fetch(choiceForm.action, {method: 'POST', headers: {Accept: 'application/json'}, body: data});
            if (!result.ok) throw Error();
            enabled = result.headers.get('X-Analytics-Choice') === 'allow' && !privateMode;
            panel.hidden = true;
            error.hidden = true;
        } catch {
            error.hidden = false;
        } finally {
            buttons.forEach(b => { b.disabled = false; });
        }
    });

    function send(kind, fields) {
        if (!enabled || !window.crypto?.randomUUID) return;
        const data = new URLSearchParams({csrfmiddlewaretoken: csrf.value, id: crypto.randomUUID(), kind, ...fields});
        if (!navigator.sendBeacon || !navigator.sendBeacon(endpoint, data)) {
            fetch(endpoint, {method: 'POST', body: data, keepalive: true, credentials: 'same-origin'}).catch(() => {});
        }
    }

    function click(event) {
        const link = event.target.closest('a[href], #burger');
        if (!link || link.classList.contains('cookie-settings') || (event.type === 'auxclick' && event.button !== 1)) return;
        const section = link.closest('section,header,footer');
        const sectionId = section?.id || section?.classList[0] || '';
        const names = {top: 'Шапка', hero: 'Первый экран', products: 'Каталог', how: 'Как работаем',
            why: 'Преимущества', contact: 'Контакты', reviews: 'Отзывы', footer: 'Подвал'};
        const placement = names[sectionId] || sectionId;
        const label = (link.getAttribute('aria-label') || link.innerText || link.title || '').trim().replace(/\s+/g, ' ');
        const target = link.closest('.review-pages') ? 'review-page' : link.getAttribute('href') || 'menu';
        send('click', {placement, label, target});
    }
    document.addEventListener('click', click);
    document.addEventListener('auxclick', click);
    document.querySelector('form.form')?.addEventListener('submit', () => {
        send('click', {placement: 'Контакты', label: 'Отправить заявку', target: 'request-form'});
    });
    document.querySelector('.review-form')?.addEventListener('submit', () => {
        send('click', {placement: 'Отзывы', label: 'Отправить отзыв', target: 'review-form'});
    });
})();
