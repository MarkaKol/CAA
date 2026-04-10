(function() {
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'canvas',
            method: 'toDataURL',
            size: { width: this.width, height: this.height },
            args: args,
            timestamp: Date.now(),
            stack: new Error().stack
        }));
        return originalToDataURL.apply(this, args);
    };
    
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'canvas',
            method: 'getImageData',
            area: { x, y, w, h },
            timestamp: Date.now()
        }));
        return originalGetImageData.call(this, x, y, w, h);
    };
    
    const originalFillText = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText = function(text, x, y, maxWidth) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'canvas',
            method: 'fillText',
            text: String(text).substring(0, 50),
            position: { x, y },
            timestamp: Date.now()
        }));
        return originalFillText.call(this, text, x, y, maxWidth);
    };
    
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        const value = getParameter.call(this, param);
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'webgl',
            method: 'getParameter',
            param: param,
            value: value,
            timestamp: Date.now()
        }));
        return value;
    };
    
    const getExtension = WebGLRenderingContext.prototype.getExtension;
    WebGLRenderingContext.prototype.getExtension = function(name) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'webgl',
            method: 'getExtension',
            extension: name,
            timestamp: Date.now()
        }));
        return getExtension.call(this, name);
    };
    
    console.log('[CAA] Canvas trap injected');
})();