(function() {
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        const options = args[1] || {};
        
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'network',
            method: 'fetch',
            url: typeof url === 'string' ? url : url.url,
            method_type: options.method || 'GET',
            body: options.body ? String(options.body).substring(0, 200) : null,
            headers: options.headers,
            timestamp: Date.now()
        }));
        
        return originalFetch.apply(this, args);
    };
    
    const XHR = XMLHttpRequest.prototype;
    const originalOpen = XHR.open;
    const originalSend = XHR.send;
    const originalSetRequestHeader = XHR.setRequestHeader;
    
    XHR.open = function(method, url) {
        this._caa_method = method;
        this._caa_url = url;
        this._caa_headers = {};
        return originalOpen.apply(this, arguments);
    };
    
    XHR.setRequestHeader = function(header, value) {
        this._caa_headers[header] = value;
        return originalSetRequestHeader.apply(this, arguments);
    };
    
    XHR.send = function(body) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'network',
            method: 'xhr',
            url: this._caa_url,
            method_type: this._caa_method,
            body: body ? String(body).substring(0, 200) : null,
            headers: this._caa_headers,
            timestamp: Date.now()
        }));
        
        this.addEventListener('load', function() {
            console.log('[CAA_TRAP]', JSON.stringify({
                type: 'network_response',
                method: 'xhr',
                url: this._caa_url,
                status: this.status,
                response_size: this.responseText ? this.responseText.length : 0,
                timestamp: Date.now()
            }));
        });
        
        return originalSend.call(this, body);
    };
    
    if (window.navigator.sendBeacon) {
        const originalSendBeacon = navigator.sendBeacon;
        navigator.sendBeacon = function(url, data) {
            console.log('[CAA_TRAP]', JSON.stringify({
                type: 'network',
                method: 'beacon',
                url: url,
                data_size: data ? data.length || data.size || 0 : 0,
                timestamp: Date.now()
            }));
            return originalSendBeacon.call(this, url, data);
        };
    }
    
    if (window.WebSocket) {
        const originalWebSocket = window.WebSocket;
        window.WebSocket = function(...args) {
            console.log('[CAA_TRAP]', JSON.stringify({
                type: 'network',
                method: 'websocket',
                url: args[0],
                timestamp: Date.now()
            }));
            return new originalWebSocket(...args);
        };
        window.WebSocket.prototype = originalWebSocket.prototype;
    }
    
    console.log('[CAA] Network trap injected');
})();