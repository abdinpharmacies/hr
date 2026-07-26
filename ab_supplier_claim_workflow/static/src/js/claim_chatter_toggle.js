/** @odoo-module **/
import { registry } from "@web/core/registry";
import { onMounted, onRendered, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { _t } from "@web/core/l10n/translation";
import { user as odooUser } from "@web/core/user";
import { SccCloseErrorDialog } from "./scc_close_error_dialog";

const STORAGE_KEY = "claim_chatter_visible";
const HIDE_CHATTER_CLASS = "scc-hide-claim-chatter";

function getChatterPref() {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === null ? true : v === "true";
}
function setChatterPref(v) {
    localStorage.setItem(STORAGE_KEY, String(v));
}

// Client action handler: toggle localStorage & reload
registry.category("actions").add("toggle_claim_chatter", (env, action) => {
    setChatterPref(!getChatterPref());
    window.location.reload();
});

// Custom form controller for ab_supplier_claim_cycle
class ClaimFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            this._syncChatter();
            this._initTrackingCard();
            this._initWhatsAppFab();
        });
        onRendered(() => {
            this._syncChatter();
            this._syncWhatsAppFab();
        });
        onWillUnmount(() => {
            if (this._controlsChatterClass) {
                document.body.classList.remove(HIDE_CHATTER_CLASS);
            }
            this._cleanupTrackingCard();
            this._cleanupWhatsAppFab();
        });
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.type === "action") {
            return true;
        }
        if (clickParams.name === "action_close_claim") {
            const record = this.model?.root;
            if (!record || record.isNew || !record.resId) {
                return super.beforeExecuteActionButton(clickParams);
            }
            const errors = await this.env.services.orm.call(
                "ab_supplier_claim_cycle",
                "action_validate_close",
                [[record.resId]]
            );
            if (errors && errors.length) {
                this.env.services.dialog.add(SccCloseErrorDialog, { errors });
                return false;
            }
            return true;
        }
        return super.beforeExecuteActionButton(clickParams);
    }

    async _syncChatter() {
        if (this._isSupplierTrackingDialog()) return;
        this._controlsChatterClass = true;
        document.body.classList.toggle(HIDE_CHATTER_CLASS, !getChatterPref());
    }

    // ================================================================
    // Viewport WhatsApp Floating Action Button
    // ================================================================

    _isSupplierTrackingDialog() {
        return !!this.rootRef?.el?.querySelector('[data-scc-backend-card="1"]');
    }

    _initWhatsAppFab() {
        if (this._isSupplierTrackingDialog() || this.whatsappFabEl) return;

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'scc-whatsapp-floating-btn scc-whatsapp-global-fab scc-whatsapp-fab-hidden';
        button.setAttribute('aria-label', _t('Send WhatsApp Message'));
        button.setAttribute('title', _t('Send WhatsApp Message'));

        const icon = document.createElement('span');
        icon.className = 'scc-whatsapp-floating-icon';
        icon.textContent = '💬';

        const label = document.createElement('span');
        label.className = 'scc-whatsapp-floating-label';
        label.textContent = _t('Send WhatsApp Message');

        button.append(icon, label);
        document.body.appendChild(button);

        this.whatsappFabEl = button;
        this._whatsappFabClick = (ev) => this._onWhatsAppFabClick(ev);
        this._whatsappFabHover = () => this._openWhatsAppFabPreview();
        button.addEventListener('click', this._whatsappFabClick);
        button.addEventListener('mouseenter', this._whatsappFabHover);
        button.addEventListener('focusin', this._whatsappFabHover);
        this._syncWhatsAppFabDirection();
        this._syncWhatsAppFab();
    }

    _cleanupWhatsAppFab() {
        if (!this.whatsappFabEl) return;
        clearTimeout(this._whatsappFabPreviewTimer);
        this.whatsappFabEl.removeEventListener('click', this._whatsappFabClick);
        this.whatsappFabEl.removeEventListener('mouseenter', this._whatsappFabHover);
        this.whatsappFabEl.removeEventListener('focusin', this._whatsappFabHover);
        this.whatsappFabEl.remove();
        this.whatsappFabEl = null;
        this._whatsappFabClick = null;
        this._whatsappFabHover = null;
        this._whatsappFabPreviewTimer = null;
        this._whatsappSyncToken = 0;
    }

    _openWhatsAppFabPreview() {
        if (!this.whatsappFabEl) return;
        clearTimeout(this._whatsappFabPreviewTimer);
        this.whatsappFabEl.classList.add('scc-whatsapp-fab-expanded');
        this._whatsappFabPreviewTimer = setTimeout(() => {
            if (this.whatsappFabEl) {
                this.whatsappFabEl.classList.remove('scc-whatsapp-fab-expanded');
            }
        }, 3000);
    }

    _hasWhatsAppFabGroup() {
        if (!this._whatsappGroupPromise) {
            this._whatsappGroupPromise = Promise.all([
                odooUser.hasGroup('ab_supplier_claim_cycle.supplier_claim_group_user'),
                odooUser.hasGroup('ab_supplier_claim_cycle.supplier_claim_group_admin'),
            ]).then(([isSecretarial, isAdmin]) => isSecretarial || isAdmin);
        }
        return this._whatsappGroupPromise;
    }

    async _shouldShowWhatsAppFab() {
        const record = this.model?.root;
        if (!record || record.isNew || !record.resId || this._isSupplierTrackingDialog()) {
            return false;
        }
        const data = record.data || {};
        if (!data.supplier_notified || !['supplier_notification', 'delivery'].includes(data.status) || !data.contact_phone) {
            return false;
        }
        if (!['check_delivered', 'mixed'].includes(data.check_delivery_status)) {
            return false;
        }
        return this._hasWhatsAppFabGroup();
    }

    async _syncWhatsAppFab() {
        if (!this.whatsappFabEl) return;
        this._syncWhatsAppFabDirection();
        const token = (this._whatsappSyncToken || 0) + 1;
        this._whatsappSyncToken = token;
        const shouldShow = await this._shouldShowWhatsAppFab();
        if (token !== this._whatsappSyncToken || !this.whatsappFabEl) return;
        this.whatsappFabEl.classList.toggle('scc-whatsapp-fab-hidden', !shouldShow);
    }

    _syncWhatsAppFabDirection() {
        if (!this.whatsappFabEl) return;
        const html = document.documentElement;
        const body = document.body;
        const lang = (
            html.getAttribute('lang')
            || body.getAttribute('lang')
            || odooUser.context?.lang
            || odooUser.lang
            || ''
        ).toLowerCase();
        const dir = (
            html.getAttribute('dir')
            || body.getAttribute('dir')
            || ''
        ).toLowerCase();
        const isRtl = (
            dir === 'rtl'
            || html.classList.contains('o_rtl')
            || body.classList.contains('o_rtl')
            || lang.startsWith('ar')
        );
        this.whatsappFabEl.classList.remove('rtl', 'ltr', 'scc-whatsapp-fab-rtl', 'scc-whatsapp-fab-ltr');
        this.whatsappFabEl.classList.add(isRtl ? 'rtl' : 'ltr');
        this.whatsappFabEl.setAttribute('dir', isRtl ? 'rtl' : 'ltr');
        const offset = 'var(--scc-whatsapp-fab-offset, 28px)';
        if (isRtl) {
            this.whatsappFabEl.style.setProperty('left', `calc(${offset} + env(safe-area-inset-left, 0px))`, 'important');
            this.whatsappFabEl.style.setProperty('right', 'auto', 'important');
        } else {
            this.whatsappFabEl.style.setProperty('right', `calc(${offset} + env(safe-area-inset-right, 0px))`, 'important');
            this.whatsappFabEl.style.setProperty('left', 'auto', 'important');
        }
    }

    async _onWhatsAppFabClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const record = this.model?.root;
        if (!record || record.isNew || !record.resId) return;

        const saved = await record.save({ reload: false });
        if (saved === false) return;

        const action = await this.orm.call(
            'ab_supplier_claim_cycle',
            'action_open_supplier_whatsapp',
            [[record.resId]]
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    // ================================================================
    // Premium Tracking Card — Backend Interactions
    // ================================================================

    _initTrackingCard() {
        this.cardEl = this.rootRef?.el?.querySelector('[data-scc-backend-card="1"]');
        if (!this.cardEl) return;
        document.body.classList.add('scc-premium-dialog-open');
        this._cardState = { shareOpen: false, visitsOpen: false, visitsLoaded: false };
        this._cardCleanups = [];

        this._initExpiryRing();
        this._initSharePopover();
        this._initDownloadQR();
        this._initPreviewQR();
        this._initCloseDialog();
        this._initRippleEffect();
        this._initAutoSelectUrl();
        this._initCopyUrlButton();
    }

    _cleanupTrackingCard() {
        if (this._cardCleanup) this._cardCleanup();
        for (const cleanup of this._cardCleanups || []) cleanup();
        document.body.classList.remove('scc-premium-dialog-open');
        this.cardEl = null;
        this._cardState = null;
        this._cardCleanups = null;
    }

    _registerCardCleanup(cleanup) {
        if (!this._cardCleanups) this._cardCleanups = [];
        this._cardCleanups.push(cleanup);
    }

    /** ---- Status Chip & Ring (always green) ---- */
    _initExpiryRing() {
        const ringProgress = this.cardEl.querySelector('[data-scc-ring-progress="1"]');
        const ringTooltip = this.cardEl.querySelector('[data-scc-qr-ring-tooltip="1"]');
        const statusChip = this.cardEl.querySelector('[data-scc-status-chip="1"]');

        if (ringProgress) {
            ringProgress.style.strokeDashoffset = '0';
            ringProgress.classList.remove('is-warning', 'is-danger');
        }
        if (ringTooltip) {
            ringTooltip.textContent = '✓ Token Active';
        }
        if (statusChip) {
            const isOnline = this.model?.root?.data?.tracking_is_online;
            const chipText = statusChip.querySelector('.scc-chip-text');
            if (chipText) chipText.textContent = isOnline ? 'Online' : 'Offline';
            statusChip.classList.toggle('is-active', !!isOnline);
        }
    }

    /** ---- Toast Notification ---- */
    _showToast(message, icon) {
        const existing = document.querySelector('.scc-backend-toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.className = 'scc-backend-toast';
        toast.innerHTML = `<span class="scc-backend-toast-icon">${icon || '✓'}</span> ${message}`;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('is-visible'));
        setTimeout(() => {
            toast.classList.remove('is-visible');
            setTimeout(() => toast.remove(), 450);
        }, 2500);
    }

    /** ---- Get QR Image Source ---- */
    _getQRSrc() {
        const img = this.cardEl.querySelector('.scc-dialog-qr-img img');
        return img ? img.src : '';
    }

    /** ---- Get Tracking URL from Record ---- */
    _getTrackingURL() {
        const fieldEl = this.cardEl.querySelector('.scc-dialog-url-field .o_field_copy');
        if (fieldEl) return fieldEl.textContent.trim();
        const inputEl = this.cardEl.querySelector('.scc-dialog-url-field input');
        return inputEl ? inputEl.value : this.model?.root?.data?.tracking_url || '';
    }

    _escapeHTML(value) {
        const el = document.createElement('div');
        el.textContent = value || '';
        return el.innerHTML;
    }

    _maskToken(value) {
        if (!value) return '••••••••••••';
        return value.length > 8 ? `${value.slice(0, 4)}••••••••${value.slice(-4)}` : '••••••••••••';
    }

    _formatVisitDate(value, options) {
        if (!value) return '—';
        const text = String(value);
        const date = value instanceof Date ? value : new Date(text.replace(' ', 'T') + 'Z');
        if (Number.isNaN(date.getTime())) return text;
        return date.toLocaleString(undefined, options);
    }

    _parseUserAgent(value) {
        const ua = value || '';
        let browser = _t('Unknown Browser');
        let os = _t('Unknown Device');

        const browserMatch = ua.match(/(Edg|Chrome|Firefox|Safari|OPR|Opera)\/([0-9.]+)/);
        if (browserMatch) {
            const browserMap = { Edg: 'Edge', OPR: 'Opera' };
            browser = `${browserMap[browserMatch[1]] || browserMatch[1]} ${browserMatch[2].split('.')[0]}`;
        }

        if (/Windows NT 10/.test(ua)) {
            os = 'Windows 11 / 10';
        } else if (/Windows/.test(ua)) {
            os = 'Windows';
        } else if (/Android/.test(ua)) {
            os = 'Android';
        } else if (/iPhone|iPad|iOS/.test(ua)) {
            os = 'iOS';
        } else if (/Mac OS X/.test(ua)) {
            os = 'macOS';
        } else if (/Linux/.test(ua)) {
            os = 'Linux';
        }
        return { browser, os, label: `${browser} • ${os}` };
    }

    _getSupplierName() {
        const supplier = this.model?.root?.data?.supplier_id;
        if (Array.isArray(supplier)) return supplier[1] || _t('Supplier Visitor');
        if (supplier?.display_name) return supplier.display_name;
        return _t('Supplier Visitor');
    }

    _initVisitsDrawer() {
        const drawer = this.cardEl.querySelector('[data-scc-visits-drawer="1"]');
        const container = this.cardEl.querySelector('[data-scc-visits-accordion="1"]');
        const recordId = this.model?.root?.resId;
        if (!drawer || !container || !recordId) return;

        const toggle = drawer.querySelector('[data-scc-visits-drawer-toggle="1"]');
        const collapse = drawer.querySelector('[data-scc-visits-drawer-collapse="1"]');
        const badge = drawer.querySelector('[data-scc-visits-badge="1"]');
        const initialCount = this.model?.root?.data?.tracking_visit_count || 0;
        this._updateVisitsBadge(badge, 0);

        const openDrawer = async (ev) => {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                this._addRipple(ev, toggle || drawer);
            }
            if (this._cardState.visitsOpen) {
                closeDrawer();
                return;
            }
            drawer.classList.add('is-open');
            this._cardState.visitsOpen = true;
            if (!this._cardState.visitsLoaded) {
                await this._loadVisitsAccordion(container, recordId);
            }
        };

        const closeDrawer = () => {
            drawer.classList.add('is-closing');
            drawer.classList.remove('is-open');
            this._cardState.visitsOpen = false;
            setTimeout(() => drawer.classList.remove('is-closing'), 360);
        };

        toggle?.addEventListener('click', openDrawer);
        collapse?.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            closeDrawer();
        });

        const poll = setInterval(async () => {
            try {
                const currentCount = await this.env.services.orm.searchCount(
                    'ab.supplier.claim.tracking.visit',
                    [['claim_id', '=', recordId]]
                );
                this._updateVisitsBadge(badge, Math.max(currentCount - initialCount, 0));
            } catch {
                this._updateVisitsBadge(badge, 0);
            }
        }, 30000);

        this._registerCardCleanup(() => clearInterval(poll));
    }

    async _loadVisitsAccordion(container, recordId) {
        container.innerHTML = `
            <div class="scc-visits-loading">
                <div class="scc-visit-skeleton"></div>
                <div class="scc-visit-skeleton"></div>
            </div>
        `;
        let visits = [];
        try {
            visits = await this.env.services.orm.searchRead(
                'ab.supplier.claim.tracking.visit',
                [['claim_id', '=', recordId]],
                ['visit_date', 'ip_address', 'user_agent'],
                { order: 'visit_date desc, id desc', limit: 50 }
            );
        } catch {
            container.innerHTML = this._renderVisitsEmptyState();
            this._cardState.visitsLoaded = true;
            return;
        }
        if (!visits.length) {
            container.innerHTML = this._renderVisitsEmptyState();
            this._cardState.visitsLoaded = true;
            return;
        }
        this._renderVisitsAccordion(container, visits, false);
        this._cardState.visitsLoaded = true;
    }

    _updateVisitsBadge(badge, count) {
        if (!badge) return;
        badge.textContent = count > 9 ? '9+' : String(count);
        badge.classList.toggle('is-visible', count > 0);
    }

    _renderVisitsEmptyState() {
        return `
            <div class="scc-visits-empty">
                <div class="scc-visits-empty-icon">👀</div>
                <div class="scc-visits-empty-title">${this._escapeHTML(_t('No supplier visits yet'))}</div>
                <div class="scc-visits-empty-sub">${this._escapeHTML(_t("The tracking link hasn't been opened."))}</div>
            </div>
        `;
    }

    _renderVisitsAccordion(container, visits, showAll) {
        const visibleVisits = showAll ? visits : visits.slice(0, 5);
        const supplierName = this._escapeHTML(this._getSupplierName());
        const token = this._maskToken(this.model?.root?.data?.tracking_token || '');
        const online = !!this.model?.root?.data?.tracking_is_online;
        const visitCards = visibleVisits.map((visit, index) => {
            const device = this._parseUserAgent(visit.user_agent);
            const summaryDate = this._formatVisitDate(visit.visit_date, {
                day: 'numeric',
                month: 'short',
                hour: 'numeric',
                minute: '2-digit',
            });
            const detailDate = this._formatVisitDate(visit.visit_date, {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                second: '2-digit',
            });
            const isOnline = online && index === 0;
            return `
                <button type="button" class="scc-visit-card" data-scc-visit-card="1" data-index="${index}">
                    <div class="scc-visit-summary">
                        <div class="scc-visit-main">
                            <div class="scc-visit-title-row">
                                <span class="scc-visit-globe">🌍</span>
                                <span class="scc-visit-name">${supplierName}</span>
                            </div>
                            <div class="scc-visit-time">${this._escapeHTML(summaryDate)}</div>
                            <div class="scc-visit-device">${this._escapeHTML(device.label)}</div>
                        </div>
                        <div class="scc-visit-side">
                            <span class="scc-visit-status ${isOnline ? 'is-online' : 'is-offline'}">
                                <span class="scc-visit-status-dot"></span>
                                ${this._escapeHTML(isOnline ? _t('Online') : _t('Offline'))}
                            </span>
                            <span class="scc-visit-chevron">⌄</span>
                        </div>
                    </div>
                    <div class="scc-visit-detail" data-scc-visit-detail="1"
                         data-ip="${this._escapeHTML(visit.ip_address || '—')}"
                         data-device="${this._escapeHTML(device.label)}"
                         data-time="${this._escapeHTML(detailDate)}"
                         data-token="${this._escapeHTML(token)}"></div>
                </button>
            `;
        }).join('');

        container.innerHTML = `
            <div class="scc-visits-accordion">
                ${visitCards}
            </div>
            ${visits.length > 5 ? `
                <button type="button" class="scc-visits-toggle" data-scc-visits-toggle="1">
                    ${this._escapeHTML(showAll ? _t('Show Less') : _t('View All Visits'))}
                </button>
            ` : ''}
        `;

        this._bindVisitsAccordion(container, visits, showAll);
    }

    _bindVisitsAccordion(container, visits, showAll) {
        const cards = [...container.querySelectorAll('[data-scc-visit-card="1"]')];
        for (const card of cards) {
            card.addEventListener('click', (ev) => {
                this._addRipple(ev, card);
                const wasOpen = card.classList.contains('is-open');
                for (const other of cards) {
                    if (other !== card) this._closeVisitCard(other);
                }
                if (wasOpen) {
                    this._closeVisitCard(card);
                } else {
                    this._openVisitCard(card);
                }
            });
        }
        const toggle = container.querySelector('[data-scc-visits-toggle="1"]');
        if (toggle) {
            toggle.addEventListener('click', (ev) => {
                ev.preventDefault();
                this._addRipple(ev, toggle);
                this._renderVisitsAccordion(container, visits, !showAll);
            });
        }
    }

    _openVisitCard(card) {
        const detail = card.querySelector('[data-scc-visit-detail="1"]');
        if (!detail) return;
        if (!detail.dataset.rendered) {
            detail.innerHTML = `
                <div class="scc-visit-detail-grid">
                    <div class="scc-visit-detail-item">
                        <span class="scc-visit-detail-icon">🌐</span>
                        <span class="scc-visit-detail-label">${this._escapeHTML(_t('IP Address'))}</span>
                        <span class="scc-visit-detail-value">${detail.dataset.ip}</span>
                    </div>
                    <div class="scc-visit-detail-item">
                        <span class="scc-visit-detail-icon">📱</span>
                        <span class="scc-visit-detail-label">${this._escapeHTML(_t('Device'))}</span>
                        <span class="scc-visit-detail-value">${detail.dataset.device}</span>
                    </div>
                    <div class="scc-visit-detail-item">
                        <span class="scc-visit-detail-icon">🕒</span>
                        <span class="scc-visit-detail-label">${this._escapeHTML(_t('Visit Time'))}</span>
                        <span class="scc-visit-detail-value">${detail.dataset.time}</span>
                    </div>
                    <div class="scc-visit-detail-item">
                        <span class="scc-visit-detail-icon">🔗</span>
                        <span class="scc-visit-detail-label">${this._escapeHTML(_t('Tracking Token'))}</span>
                        <span class="scc-visit-detail-value">${detail.dataset.token}</span>
                    </div>
                </div>
            `;
            detail.dataset.rendered = '1';
        }
        card.classList.add('is-open');
        detail.style.maxHeight = `${detail.scrollHeight}px`;
    }

    _closeVisitCard(card) {
        const detail = card.querySelector('[data-scc-visit-detail="1"]');
        card.classList.remove('is-open');
        if (detail) detail.style.maxHeight = '0px';
    }

    _addRipple(ev, target) {
        const ripple = document.createElement('span');
        const rect = target.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        ripple.className = 'scc-visit-ripple';
        ripple.style.width = ripple.style.height = `${size}px`;
        ripple.style.left = `${ev.clientX - rect.left - size / 2}px`;
        ripple.style.top = `${ev.clientY - rect.top - size / 2}px`;
        target.appendChild(ripple);
        ripple.addEventListener('animationend', () => ripple.remove(), { once: true });
    }

    /** ---- Download QR ---- */
    _initDownloadQR() {
        const downloadBtn = this.cardEl.querySelector('[data-scc-download-qr="1"]');
        if (!downloadBtn) return;
        downloadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const src = this._getQRSrc();
            if (!src) {
                this._showToast(_t('QR code not available'), '⚠');
                return;
            }
            const a = document.createElement('a');
            a.href = src;
            a.download = 'supplier-claim-qr.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            this._closeShare();
            this._showToast(_t('QR Code Downloaded'), '⬇');
        });
    }

    /** ---- Preview QR Full Size ---- */
    _initPreviewQR() {
        const previewBtn = this.cardEl.querySelector('[data-scc-preview-qr="1"]');
        if (!previewBtn) return;
        previewBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const src = this._getQRSrc();
            if (!src) {
                this._showToast(_t('QR code not available'), '⚠');
                return;
            }
            const overlay = document.createElement('div');
            overlay.className = 'scc-backend-preview-overlay';
            overlay.innerHTML = `
                <div class="scc-backend-preview-content">
                    <img class="scc-backend-preview-image" src="${src}" alt="${_t('QR Code Full Size')}"/>
                    <button type="button" class="scc-backend-preview-close">${_t('Close')}</button>
                </div>
            `;
            document.body.appendChild(overlay);
            requestAnimationFrame(() => overlay.classList.add('is-visible'));

            const closePreview = () => {
                document.removeEventListener('keydown', handler);
                overlay.classList.remove('is-visible');
                overlay.addEventListener('transitionend', () => overlay.remove(), { once: true });
            };
            overlay.addEventListener('click', (ev) => { if (ev.target === overlay) closePreview(); });
            overlay.querySelector('.scc-backend-preview-close').addEventListener('click', closePreview);
            const handler = (ev) => { if (ev.key === 'Escape') closePreview(); };
            document.addEventListener('keydown', handler);
            this._closeShare();
        });
    }

    /** ---- Share Popover ---- */
    _initSharePopover() {
        const shareBtn = this.cardEl.querySelector('[data-scc-share-btn="1"]');
        const popover = this.cardEl.querySelector('[data-scc-share-popover="1"]');
        if (!shareBtn || !popover) return;

        const toggleShare = (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            this._cardState.shareOpen = !this._cardState.shareOpen;
            popover.classList.toggle('is-visible', this._cardState.shareOpen);
            shareBtn.classList.toggle('is-open', this._cardState.shareOpen);
        };
        const closeShare = () => {
            this._cardState.shareOpen = false;
            popover.classList.remove('is-visible');
            shareBtn.classList.remove('is-open');
        };
        this._closeShare = closeShare;

        shareBtn.addEventListener('click', toggleShare);

        // Click outside to close
        const outsideHandler = (e) => {
            if (this._cardState.shareOpen && !popover.contains(e.target) && !shareBtn.contains(e.target)) {
                closeShare();
            }
        };
        document.addEventListener('click', outsideHandler);

        // Escape to close
        const escHandler = (e) => {
            if (e.key === 'Escape' && this._cardState.shareOpen) {
                closeShare();
                shareBtn.focus();
            }
        };
        document.addEventListener('keydown', escHandler);

        this._cardCleanup = () => {
            document.removeEventListener('click', outsideHandler);
            document.removeEventListener('keydown', escHandler);
        };

        // Share options
        const options = popover.querySelectorAll('[data-scc-share]');
        options.forEach((opt) => {
            opt.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const action = opt.dataset.sccShare;
                const url = this._getTrackingURL();
                const qrSrc = this._getQRSrc();

                switch (action) {
                    case 'copy':
                        this._copyToClipboard(url).then(() => {
                            this._showToast(_t('Secure Link Copied'), '✓');
                        }).catch(() => {});
                        break;
                    case 'open':
                        if (url) window.open(url, '_blank');
                        break;
                    case 'download-qr':
                        if (qrSrc) {
                            const a = document.createElement('a');
                            a.href = qrSrc;
                            a.download = 'supplier-claim-qr.png';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            this._showToast(_t('QR Code Downloaded'), '⬇');
                        }
                        break;
                    case 'email':
                        if (url) window.location.href = `mailto:?subject=${encodeURIComponent(_t('Supplier Claim Tracking'))}&body=${encodeURIComponent(_t('Track your claim here: ') + url)}`;
                        break;
                    case 'whatsapp':
                        if (url) window.open(`https://wa.me/?text=${encodeURIComponent(_t('Track your supplier claim: ') + url)}`, '_blank');
                        break;
                }
                closeShare();
            });
        });
    }

    /** ---- Close Dialog ---- */
    _initCloseDialog() {
        const btns = this.cardEl.querySelectorAll('[data-scc-dialog-close="1"]');
        if (!btns.length) return;
        const close = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.env.services.action.doAction({ type: "ir.actions.act_window_close" });
        };
        btns.forEach((btn) => btn.addEventListener('click', close));
    }

    /** ---- Ripple Effect on Primary Button ---- */
    _initRippleEffect() {
        const btn = this.cardEl.querySelector('[data-scc-share-btn="1"]');
        if (!btn) return;
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            const ripple = document.createElement('span');
            ripple.className = 'scc-dialog-ripple';
            ripple.style.width = ripple.style.height = `${size}px`;
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            btn.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove());
        });
    }

    /** ---- Auto-select URL on click ---- */
    _initAutoSelectUrl() {
        const urlWrap = this.cardEl.querySelector('.scc-dialog-url-wrap');
        if (!urlWrap) return;
        urlWrap.addEventListener('click', () => {
            const input = urlWrap.querySelector('input');
            if (input) {
                input.focus();
                input.select();
                return;
            }
            const copyField = urlWrap.querySelector('.o_field_copy');
            if (!copyField) return;
            const range = document.createRange();
            range.selectNodeContents(copyField);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            this._showToast(_t('URL selected'), '↗');
        });
    }

    _copyToClipboard(value) {
        if (!value) return Promise.reject();
        if (navigator.clipboard?.writeText) {
            return navigator.clipboard.writeText(value);
        }
        const textarea = document.createElement('textarea');
        textarea.value = value;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            return Promise.resolve();
        } finally {
            document.body.removeChild(textarea);
        }
    }

    /** ---- Copy URL icon button ---- */
    _initCopyUrlButton() {
        const copyBtn = this.cardEl.querySelector('[data-scc-copy-url="1"]');
        if (!copyBtn) return;
        copyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const url = this._getTrackingURL();
            if (!url) return;
            this._copyToClipboard(url).then(() => {
                this._showToast(_t('Secure Link Copied'), '✓');
            }).catch(() => {});
        });

        const openBtn = this.cardEl.querySelector('[data-scc-open-url="1"]');
        if (!openBtn) return;
        openBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const url = this._getTrackingURL();
            if (url) window.open(url, '_blank');
        });
    }

    _closeShare() {
        // will be assigned in _initSharePopover
    }
}

// Register custom form view
const claimFormView = {
    ...formView,
    Controller: ClaimFormController,
};
registry.category("views").add("ab_supplier_claim_cycle_form", claimFormView);
