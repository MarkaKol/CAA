(function() {
    const logs = [];
    const sendLog = (entry) => {
        logs.push(entry);
        console.log('[CAA_TRAP]', JSON.stringify(entry));
    };
    
    const nativeNavigator = window.navigator;
    const navigatorProxy = new Proxy(nativeNavigator, {
        get(target, prop) {
            const value = target[prop];
            sendLog({
                type: 'navigator',
                property: prop,
                value: typeof value === 'function' ? 'function' : String(value),
                timestamp: Date.now(),
                stack: new Error().stack
            });
            return value;
        }
    });
    
    const screenProxy = new Proxy(window.screen, {
        get(target, prop) {
            sendLog({
                type: 'screen',
                property: prop,
                value: target[prop],
                timestamp: Date.now()
            });
            return target[prop];
        }
    });
    
    const performanceProxy = new Proxy(window.performance, {
        get(target, prop) {
            if (prop === 'now' || prop === 'timing' || prop === 'navigation') {
                sendLog({
                    type: 'timing',
                    property: prop,
                    timestamp: Date.now()
                });
            }
            return target[prop];
        }
    });
    
    Object.defineProperty(window, 'navigator', {
        get: () => navigatorProxy,
        configurable: false
    });
    
    Object.defineProperty(window, 'screen', {
        get: () => screenProxy,
        configurable: false
    });
    
    Object.defineProperty(window, 'performance', {
        get: () => performanceProxy,
        configurable: false
    });
    
    const originalAddEventListener = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(type, listener, options) {
        if (type === 'mousemove' || type === 'keydown' || type === 'wheel' || type === 'touchstart') {
            sendLog({
                type: 'event_listener',
                eventType: type,
                target: this.tagName || this.constructor.name,
                timestamp: Date.now()
            });
        }
        return originalAddEventListener.call(this, type, listener, options);
    };
    
    console.log('[CAA] Trap injected successfully');
})();