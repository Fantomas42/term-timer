document.addEventListener('DOMContentLoaded', function() {
    const copiers = document.querySelectorAll('.algorithm-copy');

    copiers.forEach(copier => {
        copier.addEventListener('click', function() {
            const moves = copier.dataset.algorithm.trim().replace(/\s\s+/g, ' ');

            navigator.clipboard.writeText(moves).then(() => {
                this.innerHTML = '<i class="fas fa-clipboard"></i> Copied !';
                setTimeout(() => {
                    this.innerHTML = '<i class="fas fa-copy"></i> Copy';
                }, 2000);
            }).catch(err => {
                console.error('Copy error: ', err);
            });
        });
    });
});

function updateUrlParams(params) {
    const url = new URL(window.location);

    for (const [key, value] of Object.entries(params)) {
        if (value) {
            url.searchParams.set(key, value);
        } else {
            url.searchParams.delete(key);
        }
    }

    window.location.href = url.toString();
}
