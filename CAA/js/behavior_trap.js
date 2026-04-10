(function() {
    let mouseMovements = [];
    let keyPresses = [];
    let scrollEvents = [];
    let startTime = Date.now();
    
    document.addEventListener('mousemove', function(e) {
        const event = {
            type: 'mousemove',
            x: e.clientX,
            y: e.clientY,
            timestamp: Date.now(),
            timeSinceStart: Date.now() - startTime
        };
        mouseMovements.push(event);
        
        if (mouseMovements.length % 10 === 0) {
            console.log('[CAA_TRAP]', JSON.stringify({
                type: 'behavior',
                subtype: 'mouse_batch',
                count: mouseMovements.length,
                last_position: { x: e.clientX, y: e.clientY },
                timestamp: Date.now()
            }));
        }
    });
    
    document.addEventListener('keydown', function(e) {
        const event = {
            type: 'keydown',
            key: e.key,
            code: e.code,
            timestamp: Date.now()
        };
        keyPresses.push(event);
        
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'behavior',
            subtype: 'keypress',
            key: e.key,
            code: e.code,
            timestamp: Date.now()
        }));
    });
    
    document.addEventListener('wheel', function(e) {
        const event = {
            type: 'wheel',
            deltaX: e.deltaX,
            deltaY: e.deltaY,
            timestamp: Date.now()
        };
        scrollEvents.push(event);
        
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'behavior',
            subtype: 'scroll',
            delta: { x: e.deltaX, y: e.deltaY },
            timestamp: Date.now()
        }));
    });
    
    document.addEventListener('click', function(e) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'behavior',
            subtype: 'click',
            position: { x: e.clientX, y: e.clientY },
            target: e.target.tagName,
            timestamp: Date.now()
        }));
    });
    
    setInterval(function() {
        if (mouseMovements.length > 0 || keyPresses.length > 0 || scrollEvents.length > 0) {
            console.log('[CAA_TRAP]', JSON.stringify({
                type: 'behavior_summary',
                mouse_count: mouseMovements.length,
                key_count: keyPresses.length,
                scroll_count: scrollEvents.length,
                duration_seconds: (Date.now() - startTime) / 1000,
                timestamp: Date.now()
            }));
        }
    }, 5000);
    
    const originalRequestAnimationFrame = window.requestAnimationFrame;
    window.requestAnimationFrame = function(callback) {
        console.log('[CAA_TRAP]', JSON.stringify({
            type: 'behavior',
            subtype: 'raf',
            timestamp: Date.now()
        }));
        return originalRequestAnimationFrame.call(this, callback);
    };
    
    console.log('[CAA] Behavior trap injected');
})();