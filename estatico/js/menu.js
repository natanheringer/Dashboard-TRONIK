/*
Menu Hambúrguer - Dashboard-TRONIK
==================================
Gerencia o menu hambúrguer responsivo.
*/

document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.getElementById('menu-toggle');
    const menuClose = document.getElementById('menu-close');
    const menuMobile = document.getElementById('nav-menu-mobile');
    const menuOverlay = document.getElementById('menu-overlay');
    const body = document.body;
    
    if (!menuToggle || !menuMobile) return;
    
    function abrirMenu() {
        menuMobile.classList.add('active');
        if (menuOverlay) menuOverlay.classList.add('active');
        body.style.overflow = 'hidden'; // Prevenir scroll quando menu aberto
    }
    
    function fecharMenu() {
        menuMobile.classList.remove('active');
        if (menuOverlay) menuOverlay.classList.remove('active');
        body.style.overflow = '';
    }
    
    // Abrir menu
    if (menuToggle) {
        menuToggle.addEventListener('click', abrirMenu);
    }
    
    // Fechar menu
    if (menuClose) {
        menuClose.addEventListener('click', fecharMenu);
    }
    
    // Fechar ao clicar no overlay (mas não no menu)
    if (menuOverlay) {
        menuOverlay.addEventListener('click', function(e) {
            e.stopPropagation(); // Previne propagação
            fecharMenu();
        });
    }
    
    // Prevenir que cliques no menu fechem o menu
    if (menuMobile) {
        menuMobile.addEventListener('click', function(e) {
            e.stopPropagation(); // Previne que o clique se propague para o overlay
        });
    }
    
    // Fechar ao clicar em um link (mas permitir navegação)
    const menuLinks = menuMobile.querySelectorAll('.menu-mobile-link');
    menuLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            console.log('Link clicado:', link.href); // Debug
            e.stopPropagation(); // Previne propagação
            // Não fechar imediatamente, deixar o navegador seguir o link
            // O menu será fechado quando a página carregar
            setTimeout(fecharMenu, 100);
        });
        
        // Garantir que o link seja clicável
        link.style.pointerEvents = 'auto';
        link.style.cursor = 'pointer';
        link.style.position = 'relative';
        link.style.zIndex = '10000';
    });
    
    // Sincronizar badge de notificações
    const badgeMain = document.getElementById('notification-badge');
    const badgeMobile = document.getElementById('notification-badge-mobile');
    
    if (badgeMain && badgeMobile) {
        // Observar mudanças no badge principal
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    const isVisible = badgeMain.style.display !== 'none';
                    badgeMobile.style.display = isVisible ? 'inline-block' : 'none';
                    badgeMobile.textContent = badgeMain.textContent;
                }
                if (mutation.type === 'childList' || mutation.type === 'characterData') {
                    badgeMobile.textContent = badgeMain.textContent;
                }
            });
        });
        
        observer.observe(badgeMain, {
            attributes: true,
            childList: true,
            characterData: true
        });
    }
});

