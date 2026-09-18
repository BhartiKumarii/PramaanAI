import { test, expect } from '@playwright/test'

// Visual, headed walkthrough of the console against a running backend —
// logs in with the seeded demo account, then visits each console page and
// saves a screenshot. Run: npx playwright test tests/walkthrough.spec.ts --headed --workers=1
const OUT = process.env.WALK_OUT ?? 'test-results/walkthrough'
const PAGES: [string, string][] = [
  ['/console', 'dashboard'],
  ['/console/cases', 'cases'],
  ['/console/alerts', 'alerts'],
  ['/console/person-search', 'person-search'],
  ['/console/identity-network', 'identity-network'],
  ['/console/document-intelligence', 'document-intelligence'],
  ['/console/checkpoints', 'checkpoints'],
  ['/console/admin/registry', 'registry'],
  ['/console/admin/audit-logs', 'audit-logs'],
  ['/console/reports', 'reports'],
]

test.use({ viewport: { width: 1440, height: 900 }, launchOptions: { slowMo: 400 } })

test('console walkthrough', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/')
  await page.screenshot({ path: `${OUT}/00-landing.png` })
  await page.goto('/login')
  await page.fill('input[id="username"]', 'officer1')
  await page.fill('input[id="password"]', 'BorderShield123')
  await page.click('button[type="submit"]')
  await page.waitForURL(/.*console/)
  await expect(page.locator('h1').first()).toBeVisible()

  let n = 1
  for (const [path, name] of PAGES) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${OUT}/${String(n++).padStart(2, '0')}-${name}.png`, fullPage: false })
  }

  // Open the newest case from the list to show the evidence + auto-recorded note.
  await page.goto('/console/cases')
  await page.waitForLoadState('networkidle')
  const openCase = page.getByText('Open Case').first()
  if (await openCase.count()) {
    await openCase.click()
    await page.waitForURL(/.*console\/cases\/.+/)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1200)
    await page.screenshot({ path: `${OUT}/${String(n++).padStart(2, '0')}-case-detail.png`, fullPage: true })
  }
})
