(function () {
    const header = document.querySelector('.header');
    const burger = document.getElementById('burger');
    const nav = document.getElementById('nav');

    function setOpen(open) {
        header.classList.toggle('open', open);
        burger.setAttribute('aria-expanded', String(open));
    }

    burger.addEventListener('click', function () {
        setOpen(burger.getAttribute('aria-expanded') !== 'true');
    });

    nav.addEventListener('click', function (event) {
        if (event.target.closest('a')) setOpen(false);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && header.classList.contains('open')) {
            setOpen(false);
            burger.focus();
        }
    });
})();
