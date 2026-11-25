(() => {
    const prefix = '+7 (';

    function formatNumber(digits) {
        let value = prefix + digits.slice(0, 3);
        if (digits.length >= 3) value += ') ' + digits.slice(3, 6);
        if (digits.length > 6) value += '-' + digits.slice(6, 8);
        if (digits.length > 8) value += '-' + digits.slice(8, 10);
        return value;
    }

    function update(input, deleting = false) {
        const raw = input.value;
        if (!raw || /^\s*\+(?!7)/.test(raw) || !/^\s*\+?[\d\s()-]*$/.test(raw)) return;

        const caret = input.selectionStart ?? raw.length;
        const positions = Array.from(raw.matchAll(/\d/g), match => match.index);
        if (/^\s*\+7/.test(raw)) positions.shift();
        // A full domestic number may start with 8 or 7, including when pasted over the mask.
        if (positions.length === 11 && /[78]/.test(raw[positions[0]])) positions.shift();
        if (positions.length > 10) return;

        const digits = positions.map(index => raw[index]).join('');
        const formatted = !digits && deleting ? '' : formatNumber(digits);
        if (formatted === raw) return;
        input.value = formatted;
        let nextCaret = formatted.length;
        if (caret < raw.length && formatted) {
            const digitsBefore = positions.filter(index => index < caret).length;
            const national = Array.from(formatted.slice(prefix.length).matchAll(/\d/g));
            if (digitsBefore < national.length) nextCaret = prefix.length + national[digitsBefore].index;
        }
        input.setSelectionRange(nextCaret, nextCaret);
    }

    for (const input of document.querySelectorAll('input[data-ru-phone]')) {
        input.addEventListener('input', event => {
            if (!event.isComposing) update(input, event.inputType?.startsWith('delete'));
        });
        input.addEventListener('compositionend', () => update(input));
        input.addEventListener('beforeinput', event => {
            if (!['deleteContentBackward', 'deleteContentForward'].includes(event.inputType)) return;
            const value = input.value;
            const caret = input.selectionStart;
            if (caret !== input.selectionEnd || !value.startsWith(prefix)) return;
            // Let the browser delete a digit as well as the adjacent mask punctuation.
            if (event.inputType === 'deleteContentBackward') {
                let start = caret;
                while (start > prefix.length && /\D/.test(value[start - 1])) start--;
                if (start > prefix.length) input.setSelectionRange(start - 1, caret);
                else if (value === prefix) input.select();
                else event.preventDefault();
            } else {
                let end = Math.max(prefix.length, caret);
                while (end < value.length && /\D/.test(value[end])) end++;
                if (end < value.length) input.setSelectionRange(Math.max(prefix.length, caret), end + 1);
            }
        });
        input.addEventListener('paste', event => {
            if (input.value === prefix && event.clipboardData?.getData('text').trim().startsWith('+')) input.select();
        });
        input.addEventListener('blur', () => {
            if (input.value === prefix) input.value = '';
        });
        if (input.value) update(input);
    }
})();
