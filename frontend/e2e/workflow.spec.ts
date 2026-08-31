import { test, expect } from '@playwright/test'

test.describe('COSMORA End-to-End Judge Demonstration Workflow', () => {
  test('Landing Page renders mission header and navigation', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/COSMORA/i)
    await expect(page.getByText(/Paired Mechanical Experiment: Ubiquitin/i)).toBeVisible()
    await expect(page.getByText('PASSED_VALIDATION')).toBeVisible()
  })

  test('Experiment Page loads candidate selection and prediction flow', async ({ page }) => {
    await page.goto('/experiment')
    await expect(page.getByText(/APPROVED PROTEINS/i)).toBeVisible()
    await expect(page.getByText(/1UBQ/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /Estimate degradation/i })).toBeVisible()
  })

  test('Paired experiment JSON and CSV download triggers', async ({ page }) => {
    await page.goto('/')
    const jsonBtn = page.getByRole('button', { name: /JSON/i })
    const csvBtn = page.getByRole('button', { name: /CSV/i })

    await expect(jsonBtn).toBeVisible()
    await expect(csvBtn).toBeVisible()
  })
})
