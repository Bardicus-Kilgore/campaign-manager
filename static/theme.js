(function () {
  const FANTASY_TILES = Array.from({length: 12}, (_, i) =>
    `/static/bg/fantasy/tile_${String(i+1).padStart(2,'0')}.png`
  );
  const COSMIC_TILES = Array.from({length: 12}, (_, i) =>
    `/static/bg/cosmic/tile_${String(i+1).padStart(2,'0')}.png`
  );

  function pickTile(tiles) {
    return tiles[Math.floor(Math.random() * tiles.length)];
  }

  function applyTheme(theme) {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);

    if (theme === 'light') {
      root.style.setProperty('--bg-tile', `url('${pickTile(FANTASY_TILES)}')`);
    } else {
      root.style.setProperty('--bg-tile', `url('${pickTile(COSMIC_TILES)}')`);
    }

    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = theme === 'light' ? '🌙' : '☀';
    localStorage.setItem('cm-theme', theme);
  }

  // Init
  const saved = localStorage.getItem('cm-theme') || 'dark';
  applyTheme(saved);

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('themeToggle');
    if (btn) {
      btn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        applyTheme(current === 'dark' ? 'light' : 'dark');
      });
    }
  });
})();
