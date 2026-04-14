import { useState, onWillStart, useEffect } from '@odoo/owl';

import { browser } from '@web/core/browser/browser';
import { patch } from '@web/core/utils/patch';

import {ControlPanel} from '@web/search/control_panel/control_panel';

const DEFAULT_AUTOLOAD_INTERVAL_SECONDS = 5;
const AUTOLOAD_INTERACTION_GRACE_MS = 1000;
const AUTOLOAD_INTERACTION_EVENTS = [
	'pointerdown',
	'mousedown',
	'mousemove',
	'wheel',
	'keydown',
	'touchstart',
	'touchmove',
];

patch(ControlPanel.prototype, {
	setup() {
		super.setup(...arguments);
        this.autoLoadState = useState({
			active: false,
			counter: 0,
			interval: DEFAULT_AUTOLOAD_INTERVAL_SECONDS,
			lastInteractionAt: 0,
        });
		onWillStart(() => {
			this.autoLoadState.interval = this.getAutoLoadIntervalSeconds();
			if (
				this.checkAutoLoadAvailability() && 
				this.getAutoLoadStorageValue()
			) {
				this.autoLoadState.active = true;
			}
		});
		useEffect(
			() => {
				if (!this.autoLoadState.active) {
					return;
				}
				this.autoLoadState.counter = (
					this.getAutoLoadRefreshInterval()
				);
				const interval = browser.setInterval(
					() => {
						const now = Date.now();
						if (
							this.autoLoadState.lastInteractionAt &&
							now - this.autoLoadState.lastInteractionAt <= AUTOLOAD_INTERACTION_GRACE_MS
						) {
							this.autoLoadState.counter = this.getAutoLoadRefreshInterval();
							return;
						}
						this.autoLoadState.counter = (
							this.autoLoadState.counter ?
							this.autoLoadState.counter - 1 :
							this.getAutoLoadRefreshInterval()
						);
						if (this.autoLoadState.counter <= 0) {
							this.autoLoadState.counter = (
								this.getAutoLoadRefreshInterval()
							);
							this.triggerAutoLoadRefresh();
						}
					}, 
					1000
				);
				return () => browser.clearInterval(interval);
			},
			() => [this.autoLoadState.active, this.autoLoadState.interval]
		);
		useEffect(
			() => {
				if (!this.autoLoadState.active) {
					return;
				}
				const onInteraction = () => {
					const now = Date.now();
					if (
						this.autoLoadState.lastInteractionAt &&
						now - this.autoLoadState.lastInteractionAt <= AUTOLOAD_INTERACTION_GRACE_MS
					) {
						return;
					}
					this.autoLoadState.lastInteractionAt = now;
					this.autoLoadState.counter = this.getAutoLoadRefreshInterval();
				};
				for (const eventName of AUTOLOAD_INTERACTION_EVENTS) {
					window.addEventListener(eventName, onInteraction, { passive: true });
				}
				return () => {
					for (const eventName of AUTOLOAD_INTERACTION_EVENTS) {
						window.removeEventListener(eventName, onInteraction);
					}
				};
			},
			() => [this.autoLoadState.active, this.autoLoadState.interval]
		);
	},
	checkAutoLoadAvailability() {
		return ['kanban', 'list', 'form'].includes(this.env.config.viewType);
	},
    getAutoLoadRefreshInterval() {
    	return this.autoLoadState.interval || DEFAULT_AUTOLOAD_INTERVAL_SECONDS;
	},
    getAutoLoadStorageKey() {
		const keys = [
			this.env?.config?.actionId ?? '',
			this.env?.config?.viewType ?? '',
			this.env?.config?.viewId ?? '',
        ];
		return `pager_autoload:${keys.join(',')}`;
    },
    getAutoLoadIntervalStorageKey() {
		const keys = [
			this.env?.config?.actionId ?? '',
			this.env?.config?.viewType ?? '',
			this.env?.config?.viewId ?? '',
		];
		return `pager_autoload_interval:${keys.join(',')}`;
    },
    getAutoLoadStorageValue() {
    	return browser.localStorage.getItem(
        	this.getAutoLoadStorageKey()
        );
	},
    setAutoLoadStorageValue() {
    	browser.localStorage.setItem(
			this.getAutoLoadStorageKey(), true
		);
	},
    removeAutoLoadStorageValue() {
    	browser.localStorage.removeItem(
            this.getAutoLoadStorageKey()
        );
	},
    getAutoLoadIntervalSeconds() {
    	const raw = browser.localStorage.getItem(
    		this.getAutoLoadIntervalStorageKey()
		);
		const parsed = parseInt(raw, 10);
		return parsed > 0 ? parsed : DEFAULT_AUTOLOAD_INTERVAL_SECONDS;
    },
    setAutoLoadIntervalSeconds(seconds) {
    	const value = parseInt(seconds, 10);
    	const safeValue = value > 0 ? value : DEFAULT_AUTOLOAD_INTERVAL_SECONDS;
    	browser.localStorage.setItem(
    		this.getAutoLoadIntervalStorageKey(),
    		String(safeValue)
		);
    	return safeValue;
    },
    triggerAutoLoadRefresh() {
		if (this.env?.config?.viewType === 'form') {
			const model = this.env?.model;
			if (model?.load) {
				model.load();
				if (typeof model.notify === 'function') {
					model.notify();
				}
				return;
			}
			if (model?.root?.load) {
				model.root.load();
				if (typeof model.notify === 'function') {
					model.notify();
				}
				return;
			}
		}
		if (this.pagerProps?.onUpdate) {
			this.pagerProps.onUpdate({
				offset: this.pagerProps.offset,
				limit: this.pagerProps.limit
			});
		} else if (typeof this.env.searchModel?.search) {
			this.env.searchModel.search();
		}
    },
    onIntervalInput(ev) {
    	const value = this.setAutoLoadIntervalSeconds(ev.target.value);
    	this.autoLoadState.interval = value;
    	if (this.autoLoadState.active) {
    		this.autoLoadState.counter = value;
    	}
    },
	toggleAutoLoad() {
		this.autoLoadState.active = !this.autoLoadState.active;
		if (this.autoLoadState.active) {
			this.setAutoLoadStorageValue();
			this.autoLoadState.counter = this.getAutoLoadRefreshInterval();
			this.triggerAutoLoadRefresh();
		} else {
			this.removeAutoLoadStorageValue();
		}
	},
});
