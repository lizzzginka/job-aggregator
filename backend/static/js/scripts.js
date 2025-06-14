document.getElementById('archive-btn').addEventListener('click', () => {
    fetch('/archive_students', { method: 'POST' })
        .then(response => location.reload());
});

document.getElementById('show-archive-btn').addEventListener('click', () => {
    const table = document.getElementById('archive-table');
    table.style.display = table.style.display === 'none' ? 'block' : 'none';
});