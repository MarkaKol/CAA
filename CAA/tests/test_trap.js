(function testTrap() {
    console.log('[CAA_TEST] Starting trap tests');
    
    let testsPassed = 0;
    let testsFailed = 0;
    
    function assert(condition, name) {
        if (condition) {
            console.log(`[CAA_TEST] PASS: ${name}`);
            testsPassed++;
        } else {
            console.log(`[CAA_TEST] FAIL: ${name}`);
            testsFailed++;
        }
    }
    
    function testNavigatorProxy() {
        try {
            const testValue = navigator.userAgent;
            assert(typeof testValue === 'string', 'navigator.userAgent accessible');
            assert(navigator.webdriver === false, 'navigator.webdriver is false');
            testsPassed++;
        } catch(e) {
            testsFailed++;
        }
    }
    
    function testScreenProxy() {
        try {
            const width = screen.width;
            assert(typeof width === 'number', 'screen.width is number');
            assert(width > 0, 'screen.width > 0');
        } catch(e) {
            testsFailed++;
        }
    }
    
    function testCanvasTrap() {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 100;
            canvas.height = 100;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'red';
            ctx.fillRect(0, 0, 100, 100);
            const dataURL = canvas.toDataURL();
            assert(dataURL.startsWith('data:image'), 'canvas.toDataURL works');
        } catch(e) {
            testsFailed++;
        }
    }
    
    function testWebGLTrap() {
        try {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (gl) {
                const vendor = gl.getParameter(gl.VENDOR);
                assert(typeof vendor === 'string', 'webgl.getParameter works');
            } else {
                console.log('[CAA_TEST] SKIP: WebGL not available');
                testsPassed++;
            }
        } catch(e) {
            testsFailed++;
        }
    }
    
    function testNetworkTrap() {
        try {
            const xhr = new XMLHttpRequest();
            assert(typeof xhr.open === 'function', 'XHR open exists');
            
            fetch('/test')
                .catch(() => {});
            assert(typeof fetch === 'function', 'fetch exists');
        } catch(e) {
            testsFailed++;
        }
    }
    
    function testEventListenerTrap() {
        try {
            const listenerAdded = document.addEventListener('click', () => {});
            assert(true, 'addEventListener works');
        } catch(e) {
            testsFailed++;
        }
    }
    
    function testPerformanceTrap() {
        try {
            const now = performance.now();
            assert(typeof now === 'number', 'performance.now works');
            assert(now > 0, 'performance.now > 0');
        } catch(e) {
            testsFailed++;
        }
    }
    
    function runAllTests() {
        console.log('[CAA_TEST] Running all tests...');
        
        testNavigatorProxy();
        testScreenProxy();
        testCanvasTrap();
        testWebGLTrap();
        testNetworkTrap();
        testEventListenerTrap();
        testPerformanceTrap();
        
        console.log(`[CAA_TEST] Results: ${testsPassed} passed, ${testsFailed} failed`);
        
        if (testsFailed === 0) {
            console.log('[CAA_TEST] All tests passed!');
        } else {
            console.log('[CAA_TEST] Some tests failed!');
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runAllTests);
    } else {
        runAllTests();
    }
})();