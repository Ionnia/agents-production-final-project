class MemStorage {
  private m = new Map<string, string>()
  get length() { return this.m.size }
  clear() { this.m.clear() }
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null }
  setItem(k: string, v: string) { this.m.set(k, String(v)) }
  removeItem(k: string) { this.m.delete(k) }
  key(i: number) { return Array.from(this.m.keys())[i] ?? null }
}
try { globalThis.localStorage.setItem('__probe__', '1'); globalThis.localStorage.removeItem('__probe__') }
catch { Object.defineProperty(globalThis, 'localStorage', { value: new MemStorage(), writable: true, configurable: true }) }
