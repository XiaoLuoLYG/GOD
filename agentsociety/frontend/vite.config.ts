import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react-swc'

const frontendPort = Number(process.env.GOD_FRONTEND_PORT || process.env.VITE_PORT || 5174)

function resolveBase(raw = process.env.VITE_BASE || '/'): string {
    const value = raw.trim()
    if (value === '/') return '/'
    const match = value.match(/^\/proxy\/(\d+)\/?$/)
    return match ? `/proxy/${match[1]}/` : '/'
}

/** Re-add the base that code-server strips before forwarding to Vite. */
function codeServerBasePlugin(base: string): Plugin {
    if (base === '/') return { name: 'code-server-base-noop' }

    const prefix = base.slice(0, -1)
    return {
        name: 'code-server-reprefix-base',
        configureServer(server) {
            server.middlewares.use((req, _res, next) => {
                const url = req.url || '/'
                const path = url.split('?', 1)[0]
                if (
                    path === prefix
                    || path.startsWith(`${prefix}/`)
                    || path === '/api'
                    || path.startsWith('/api/')
                ) {
                    next()
                    return
                }
                req.url = `${prefix}${url.startsWith('/') ? '' : '/'}${url}`
                next()
            })
        },
    }
}

const base = resolveBase()
const hmrProtocol = process.env.VITE_HMR_PROTOCOL === 'ws' ? 'ws' : 'wss'

// https://vite.dev/config/
export default defineConfig({
    base,
    server: {
        host: process.env.VITE_HOST || '127.0.0.1',
        port: frontendPort,
        strictPort: true,
        hmr: base !== '/'
            ? {
                  protocol: hmrProtocol,
                  clientPort: Number(
                      process.env.VITE_HMR_CLIENT_PORT || (hmrProtocol === 'wss' ? 443 : 80),
                  ),
              }
            : undefined,
        proxy: {
            '/api/alipay': {
                target: 'https://agentsociety.fiblab.net',
                changeOrigin: true,
            },
            '/api/v1': {
                target: `http://127.0.0.1:${process.env.GOD_BACKEND_PORT || process.env.BACKEND_PORT || 8001}`,
                changeOrigin: true,
                ws: true,
            },
            '/api': {
                target: 'http://127.0.0.1:80',
                changeOrigin: true,
            },
        },
    },
    plugins: [codeServerBasePlugin(base), react()],
    build: {
        outDir: 'dist',
        assetsDir: 'assets',
        sourcemap: false,
    },
})
