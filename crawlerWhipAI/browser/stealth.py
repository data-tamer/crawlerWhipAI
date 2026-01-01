"""Stealth scripts for bypassing bot detection (Cloudflare, etc.)."""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Comprehensive stealth scripts to mask automation
STEALTH_SCRIPTS: List[str] = [
    # 1. Hide webdriver property
    """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });
    """,

    # 2. Override navigator.plugins to look like real browser
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
            ];
            plugins.item = (i) => plugins[i] || null;
            plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
            plugins.refresh = () => {};
            return plugins;
        },
        configurable: true
    });
    """,

    # 3. Override navigator.languages
    """
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true
    });
    """,

    # 4. Override navigator.platform
    """
    Object.defineProperty(navigator, 'platform', {
        get: () => 'Win32',
        configurable: true
    });
    """,

    # 5. Override navigator.hardwareConcurrency
    """
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true
    });
    """,

    # 6. Override navigator.deviceMemory
    """
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true
    });
    """,

    # 7. Mock chrome runtime
    """
    window.chrome = {
        runtime: {
            connect: () => {},
            sendMessage: () => {},
            onMessage: { addListener: () => {} }
        },
        loadTimes: () => {},
        csi: () => {},
        app: {}
    };
    """,

    # 8. Override permissions query
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    """,

    # 9. Override WebGL vendor/renderer
    """
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) {
            return 'Intel Inc.';
        }
        if (parameter === 37446) {
            return 'Intel Iris OpenGL Engine';
        }
        return getParameter.call(this, parameter);
    };
    """,

    # 10. Override WebGL2 vendor/renderer
    """
    if (typeof WebGL2RenderingContext !== 'undefined') {
        const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter2.call(this, parameter);
        };
    }
    """,

    # 11. Override connection info
    """
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false
        }),
        configurable: true
    });
    """,

    # 12. Remove automation indicators from window
    """
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    delete window.$cdc_asdjflasutopfhvcZLmcfl_;
    """,

    # 13. Override toString for modified functions
    """
    const nativeToString = Function.prototype.toString;
    const nativeToStringProxy = new Proxy(nativeToString, {
        apply: function(target, thisArg, args) {
            if (thisArg === navigator.permissions.query) {
                return 'function query() { [native code] }';
            }
            return Reflect.apply(target, thisArg, args);
        }
    });
    Function.prototype.toString = nativeToStringProxy;
    """,

    # 14. Override iframe contentWindow
    """
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function() {
            return window;
        }
    });
    """,

    # 15. Mock battery API
    """
    navigator.getBattery = () => Promise.resolve({
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1,
        addEventListener: () => {},
        removeEventListener: () => {}
    });
    """,
]

# Cloudflare-specific evasion scripts
CLOUDFLARE_SCRIPTS: List[str] = [
    # 1. Override Cloudflare-specific detection
    """
    // Remove Cloudflare fingerprinting hooks
    if (window.__cfBeaconQueue) {
        delete window.__cfBeaconQueue;
    }
    """,

    # 2. Simulate mouse movement patterns
    """
    // Add realistic mouse entropy
    let lastMoveTime = Date.now();
    document.addEventListener('mousemove', function(e) {
        lastMoveTime = Date.now();
    }, true);

    // Simulate occasional mouse movement
    setInterval(() => {
        if (Date.now() - lastMoveTime > 2000) {
            const event = new MouseEvent('mousemove', {
                bubbles: true,
                cancelable: true,
                clientX: Math.random() * window.innerWidth,
                clientY: Math.random() * window.innerHeight
            });
            document.dispatchEvent(event);
            lastMoveTime = Date.now();
        }
    }, 3000);
    """,

    # 3. Override screen properties
    """
    Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
    Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
    Object.defineProperty(screen, 'width', { get: () => 1920 });
    Object.defineProperty(screen, 'height', { get: () => 1080 });
    Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
    Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
    """,

    # 4. Add touch support indicators (optional, for mobile emulation)
    """
    // Indicate touch support typical of modern browsers
    Object.defineProperty(navigator, 'maxTouchPoints', {
        get: () => 0,  // Desktop
        configurable: true
    });
    """,
]


def get_stealth_scripts(include_cloudflare: bool = False) -> str:
    """
    Get combined stealth scripts as a single string.

    Args:
        include_cloudflare: Include Cloudflare-specific evasion scripts.

    Returns:
        Combined JavaScript code to inject.
    """
    scripts = STEALTH_SCRIPTS.copy()

    if include_cloudflare:
        scripts.extend(CLOUDFLARE_SCRIPTS)

    # Wrap in IIFE to avoid polluting global scope
    combined = "(function() {\n"
    combined += "\n".join(scripts)
    combined += "\n})();"

    logger.debug(f"Generated stealth script with {len(scripts)} components")
    return combined


def get_realistic_user_agent() -> str:
    """Get a realistic Chrome user agent string."""
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


def get_stealth_headers() -> dict:
    """Get headers that mimic a real browser."""
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
