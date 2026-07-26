/** @odoo-module **/

// Supplier Claim Tracking Portal — Premium Animations
// Staggered entrance, counter, and interactive effects

document.addEventListener('DOMContentLoaded', () => {
    const page = document.querySelector('.scc-portal-page');
    if (!page) return;

    const presenceUrl = page.dataset.sccPresenceUrl;

    function postPresence(online, useBeacon = false) {
        if (!presenceUrl) return;
        const body = new URLSearchParams({ online: online ? '1' : '0' });
        if (useBeacon && navigator.sendBeacon) {
            const payload = new Blob([body.toString()], {
                type: 'application/x-www-form-urlencoded;charset=UTF-8',
            });
            navigator.sendBeacon(presenceUrl, payload);
            return;
        }
        fetch(presenceUrl, {
            method: 'POST',
            body,
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            credentials: 'same-origin',
            keepalive: true,
        }).catch(() => {});
    }

    if (presenceUrl) {
        postPresence(true);
        const heartbeat = setInterval(() => postPresence(true), 30000);
        window.addEventListener('pagehide', () => {
            clearInterval(heartbeat);
            postPresence(false, true);
        });
        window.addEventListener('beforeunload', () => {
            clearInterval(heartbeat);
            postPresence(false, true);
        });
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                postPresence(true);
            }
        });
    }

    // ---- Animate progress number counting ----
    const percentEl = document.querySelector('.scc-progress-percent');
    if (percentEl) {
        const text = percentEl.textContent.trim();
        const target = parseInt(text, 10);
        if (!isNaN(target)) {
            percentEl.textContent = '0%';
            const duration = 1200;
            const start = performance.now();
            const step = (now) => {
                const elapsed = now - start;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.round(eased * target);
                percentEl.textContent = current + '%';
                if (progress < 1) {
                    requestAnimationFrame(step);
                }
            };
            requestAnimationFrame(step);
        }
    }

    // ---- Observer for card entrance (re-trigger if needed) ----
    const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            if (entry.isIntersecting) {
                entry.target.style.animationPlayState = 'running';
            }
        }
    }, { threshold: 0.1 });

    document.querySelectorAll('.scc-entrance').forEach((el) => {
        observer.observe(el);
    });

    // ---- Smooth scroll for the entire page ----
    document.documentElement.style.scrollBehavior = 'smooth';

    // ---- Theme Picker ----
    const picker = document.querySelector('.scc-theme-picker');
    const trigger = picker?.querySelector('.scc-theme-trigger');
    const menu = picker?.querySelector('.scc-theme-menu');
    const swatches = menu?.querySelectorAll('.scc-theme-swatch');
    const STORAGE_KEY = 'scc_portal_theme';

    if (picker && trigger && menu && swatches) {
        let isOpen = false;

        // Load saved theme
        const savedTheme = localStorage.getItem(STORAGE_KEY) || 'default';
        applyTheme(savedTheme);

        function applyTheme(theme) {
            document.documentElement.dataset.sccTheme = theme;
            swatches.forEach((s) => {
                const match = s.dataset.theme === theme;
                s.classList.toggle('is-active', match);
                s.setAttribute('aria-checked', String(match));
            });
            localStorage.setItem(STORAGE_KEY, theme);
        }

        function toggleMenu(e) {
            if (e) e.stopPropagation();
            isOpen = !isOpen;
            picker.classList.toggle('is-open', isOpen);
            if (isOpen) trigger.setAttribute('aria-expanded', 'true');
            else trigger.setAttribute('aria-expanded', 'false');
        }

        function closeMenu() {
            isOpen = false;
            picker.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        }

        // Trigger click
        trigger.addEventListener('click', toggleMenu);

        // Swatch click
        swatches.forEach((s) => {
            s.addEventListener('click', (e) => {
                e.stopPropagation();
                applyTheme(s.dataset.theme);
                closeMenu();
            });
        });

        // Click outside
        document.addEventListener('click', (e) => {
            if (isOpen && !picker.contains(e.target)) {
                closeMenu();
            }
        });

        // Keyboard: Escape closes
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isOpen) {
                closeMenu();
                trigger.focus();
            }
        });

        // Keyboard: Enter/Space on trigger
        trigger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleMenu();
            }
        });

        trigger.setAttribute('aria-haspopup', 'true');
        trigger.setAttribute('aria-expanded', 'false');
    }

    // ============================================================
    // Tracking Access Card — Premium Interactions
    // ============================================================

    const accessCard = document.querySelector('[data-scc-access-card]');
    if (!accessCard) return;

    const qrContainer = accessCard.querySelector('[data-scc-qr-container]');
    const qrImg = accessCard.querySelector('[data-scc-qr-img]');
    const qrRing = accessCard.querySelector('[data-scc-qr-ring]');
    const qrRingProgress = accessCard.querySelector('[data-scc-ring-progress]');
    const qrRingTooltip = accessCard.querySelector('[data-scc-qr-ring-tooltip]');
    const copyBtn = accessCard.querySelector('[data-scc-copy-link]');
    const shareBtn = accessCard.querySelector('[data-scc-share-btn]');
    const sharePopover = accessCard.querySelector('[data-scc-share-popover]');
    const shareOptions = accessCard.querySelectorAll('[data-scc-share]');
    const statusChip = accessCard.querySelector('[data-scc-status-chip]');
    const activityList = accessCard.querySelector('[data-scc-activity-list]');
    const downloadQrBtn = accessCard.querySelector('[data-scc-download-qr]');
    const previewQrBtn = accessCard.querySelector('[data-scc-preview-qr]');

    // ---- 3D Mouse Tilt Effect ----
    (function initTilt() {
        const card = accessCard;
        card.setAttribute('data-tilt', '');
        card.addEventListener('mousemove', (e) => {
            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            const rotateX = (0.5 - y) * 3;
            const rotateY = (x - 0.5) * 3;
            card.style.transform =
                `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.008)`;
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    })();

    // ---- Expiry Ring (always green) ----
    (function initExpiryRing() {
        if (qrRingProgress) {
            qrRingProgress.style.strokeDashoffset = '0';
            qrRingProgress.classList.remove('is-warning', 'is-danger');
        }
        if (qrRingTooltip) {
            qrRingTooltip.textContent = '✓ Token Active';
        }
    })();

    // ---- Toast System ----
    function showToast(message, icon) {
        const existing = document.querySelector('.scc-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'scc-toast';
        toast.innerHTML = `<span class="scc-toast-icon">${icon || '✓'}</span> ${message}`;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('is-visible'));

        setTimeout(() => {
            toast.classList.remove('is-visible');
            setTimeout(() => toast.remove(), 500);
        }, 2500);
    }

    // ---- Copy Link ----
    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            const link = accessCard.querySelector('.scc-access-link-text');
            if (!link) return;
            const text = link.textContent.trim();
            try {
                await navigator.clipboard.writeText(text);
                showToast('Secure Link Copied', '✓');
            } catch {
                showToast('Could not copy link', '⚠');
            }
        });
    }

    // ---- Share Popover ----
    let shareOpen = false;

    function toggleShare(e) {
        if (e) e.stopPropagation();
        shareOpen = !shareOpen;
        sharePopover.classList.toggle('is-visible', shareOpen);
        shareBtn.classList.toggle('is-open', shareOpen);
    }

    function closeShare() {
        shareOpen = false;
        sharePopover.classList.remove('is-visible');
        shareBtn.classList.remove('is-open');
    }

    if (shareBtn && sharePopover) {
        shareBtn.addEventListener('click', toggleShare);

        document.addEventListener('click', (e) => {
            if (shareOpen && !sharePopover.contains(e.target) && !shareBtn.contains(e.target)) {
                closeShare();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && shareOpen) {
                closeShare();
                shareBtn.focus();
            }
        });
    }

    // ---- Share Options ----
    shareOptions.forEach((opt) => {
        opt.addEventListener('click', (e) => {
            const action = opt.dataset.sccShare;
            const linkEl = accessCard.querySelector('.scc-access-link-text');
            const link = linkEl ? linkEl.textContent.trim() : '';
            const qrSrc = qrImg ? qrImg.src : '';

            switch (action) {
                case 'copy':
                    navigator.clipboard.writeText(link).then(() => {
                        showToast('Secure Link Copied', '✓');
                    }).catch(() => {});
                    break;
                case 'open':
                    window.open(link, '_blank');
                    break;
                case 'download-qr':
                    downloadQR(qrSrc);
                    break;
                case 'email':
                    window.location.href = `mailto:?subject=Supplier Claim Tracking&body=Track your claim here: ${encodeURIComponent(link)}`;
                    break;
                case 'whatsapp':
                    window.open(`https://wa.me/?text=${encodeURIComponent('Track your supplier claim: ' + link)}`, '_blank');
                    break;
                case 'telegram':
                    window.open(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=Supplier%20Claim%20Tracking`, '_blank');
                    break;
            }

            closeShare();
        });
    });

    // ---- Download QR ----
    function downloadQR(src) {
        if (!src) {
            showToast('QR code not available', '⚠');
            return;
        }
        const a = document.createElement('a');
        a.href = src;
        a.download = 'supplier-claim-qr.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('QR Code Downloaded', '⬇');
    }

    if (downloadQrBtn) {
        downloadQrBtn.addEventListener('click', () => {
            const src = qrImg ? qrImg.src : '';
            downloadQR(src);
            closeShare();
        });
    }

    // ---- Preview Full Size QR ----
    if (previewQrBtn && qrImg) {
        previewQrBtn.addEventListener('click', () => {
            const overlay = document.createElement('div');
            overlay.className = 'scc-preview-overlay';
            overlay.innerHTML = `
                <div class="scc-preview-content">
                    <img class="scc-preview-image" src="${qrImg.src}" alt="QR Code Full Size"/>
                    <button class="scc-preview-close">Close</button>
                </div>
            `;
            document.body.appendChild(overlay);
            requestAnimationFrame(() => overlay.classList.add('is-visible'));

            const closePreview = () => {
                overlay.classList.remove('is-visible');
                overlay.addEventListener('transitionend', () => overlay.remove(), { once: true });
            };

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closePreview();
            });
            overlay.querySelector('.scc-preview-close').addEventListener('click', closePreview);
            document.addEventListener('keydown', function handler(e) {
                if (e.key === 'Escape') {
                    closePreview();
                    document.removeEventListener('keydown', handler);
                }
            });
        });
    }

    // ---- Ripple Effect on Share Options ----
    shareOptions.forEach((opt) => {
        opt.addEventListener('mousemove', (e) => {
            const rect = opt.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 100;
            const y = ((e.clientY - rect.top) / rect.height) * 100;
            opt.style.setProperty('--ripple-x', x + '%');
            opt.style.setProperty('--ripple-y', y + '%');
        });
    });

    // ---- QR Hover Overlay keyboard accessibility ----
    if (qrContainer) {
        qrContainer.addEventListener('focus', () => {
            const overlay = qrContainer.querySelector('[data-scc-qr-overlay]');
            if (overlay) overlay.style.opacity = '1';
        });
        qrContainer.addEventListener('blur', () => {
            const overlay = qrContainer.querySelector('[data-scc-qr-overlay]');
            if (overlay && !qrContainer.matches(':hover')) overlay.style.opacity = '';
        });
    }

    // ---- Skeleton Loading fade-out ----
    (function initSkeleton() {
        const skeleton = accessCard.querySelector('[data-scc-skeleton]');
        if (!skeleton) return;
        const contentReadyDelay = 700;
        setTimeout(() => {
            skeleton.classList.add('is-hidden');
            skeleton.addEventListener('transitionend', () => {
                skeleton.style.display = 'none';
            }, { once: true });
        }, contentReadyDelay);
    })();

    // ---- Keyboard / Accessibility for Share ----
    if (shareBtn && sharePopover) {
        sharePopover.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeShare();
                shareBtn.focus();
            }
        });

        // Trap focus within popover when open
        const focusable = sharePopover.querySelectorAll('button');
        if (focusable.length) {
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            sharePopover.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    if (e.shiftKey && document.activeElement === first) {
                        e.preventDefault();
                        last.focus();
                    } else if (!e.shiftKey && document.activeElement === last) {
                        e.preventDefault();
                        first.focus();
                    }
                }
            });
        }
    }

    // ---- Copy Link keyboard shortcut (c) ----
    document.addEventListener('keydown', (e) => {
        if (e.key === 'c' && (e.metaKey || e.ctrlKey)) return; // let native copy pass
        if (e.key === 'c' && !e.metaKey && !e.ctrlKey && !e.target.closest('input,textarea,[contenteditable]')) {
            const link = accessCard.querySelector('.scc-access-link-text');
            if (link) {
                const text = link.textContent.trim();
                navigator.clipboard.writeText(text).then(() => {
                    showToast('Secure Link Copied', '✓');
                }).catch(() => {});
            }
        }
    });
});
