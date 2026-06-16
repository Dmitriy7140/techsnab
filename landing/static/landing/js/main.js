// Мобильное меню + закрытие по клику на ссылку.
(function () {
    var header = document.querySelector('.header');
    var burger = document.getElementById('burger');
    if (!header || !burger) return;

    burger.addEventListener('click', function () {
        header.classList.toggle('open');
    });

    document.querySelectorAll('#nav a').forEach(function (link) {
        link.addEventListener('click', function () {
            header.classList.remove('open');
        });
    });
})();
