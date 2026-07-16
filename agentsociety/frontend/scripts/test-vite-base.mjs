import assert from 'node:assert/strict'
import { once } from 'node:events'
import { spawn } from 'node:child_process'
import { get } from 'node:http'
import { createServer } from 'node:net'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const frontendDir = fileURLToPath(new URL('..', import.meta.url))
const viteBin = fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url))

async function freePort() {
  const server = createServer()
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const { port } = server.address()
  server.close()
  await once(server, 'close')
  return port
}

async function startVite(environment, viteArguments = []) {
  const port = await freePort()
  const child = spawn(
    process.execPath,
    [viteBin, '--host', '127.0.0.1', '--port', String(port), '--strictPort', ...viteArguments],
    {
      cwd: frontendDir,
      env: { ...process.env, ...environment, GOD_FRONTEND_PORT: String(port) },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  let output = ''
  child.stdout.on('data', (chunk) => { output += chunk })
  child.stderr.on('data', (chunk) => { output += chunk })

  const origin = `http://127.0.0.1:${port}`
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error(`Vite exited before becoming ready:\n${output}`)
    }
    try {
      const response = await fetch(origin)
      if (response.ok) return { child, origin }
    } catch {
      // Server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  child.kill('SIGTERM')
  throw new Error(`Timed out waiting for Vite:\n${output}`)
}

async function stopVite(child) {
  if (child.exitCode !== null) return
  child.kill('SIGTERM')
  await Promise.race([
    once(child, 'exit'),
    new Promise((resolve) => setTimeout(resolve, 2_000)),
  ])
  if (child.exitCode === null) child.kill('SIGKILL')
}

async function assertJavaScript(origin, path) {
  const response = await fetch(`${origin}${path}`)
  const body = await response.text()
  assert.equal(response.status, 200, `${path} returned ${response.status}`)
  assert.match(response.headers.get('content-type') || '', /javascript/)
  assert.doesNotMatch(body, /<!doctype html>/i, `${path} fell back to index.html`)
  return body
}

async function requestStatus(origin, host) {
  return new Promise((resolve, reject) => {
    const request = get(origin, { headers: { host } }, (response) => {
      response.resume()
      resolve(response.statusCode)
    })
    request.on('error', reject)
  })
}

test('root base serves Vite modules without an HTML fallback', async () => {
  const vite = await startVite(
    { VITE_BASE: '/', CODE_SERVER_PARENT_PID: '1' },
    ['--base', '/'],
  )
  try {
    await assertJavaScript(vite.origin, '/@vite/client')
    await assertJavaScript(vite.origin, '/src/main.tsx')
    assert.equal(await requestStatus(vite.origin, 'blocked.example.test'), 403)
  } finally {
    await stopVite(vite.child)
  }
})

test('proxy base accepts stripped requests and its explicit host and HMR settings', async () => {
  const vite = await startVite({
    VITE_BASE: '/proxy/5174/',
    VITE_HMR_PROTOCOL: 'ws',
    VITE_HMR_CLIENT_PORT: '55174',
    __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS: 'preview.example.test',
  })
  try {
    const client = await assertJavaScript(vite.origin, '/@vite/client')
    assert.match(client, /const socketProtocol = "ws"/)
    assert.match(client, /const hmrPort = 55174/)
    const response = await fetch(`${vite.origin}/pixel-town/characters/atlas.json`)
    assert.equal(response.status, 200)
    assert.match(response.headers.get('content-type') || '', /json/)
    assert.equal(await requestStatus(vite.origin, 'preview.example.test'), 200)
  } finally {
    await stopVite(vite.child)
  }
})
