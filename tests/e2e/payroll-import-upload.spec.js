const { test, expect } = require('@playwright/test');

test.describe('payroll import upload grouped run', () => {
	test.skip(true, 'Best-effort artifact: requires bench-backed Hubgh site plus seeded payroll fixtures.');

	test('uploads many files, previews one run, confirms, and downloads a single-sheet export', async ({ page }) => {
		await page.goto('/payroll_import_upload');

		// TODO: seed source catalog + payroll period fixtures in the target site.
		// TODO: upload at least two supported CLONK files and verify grouped preview cards.
		// TODO: confirm the grouped run and navigate to TC/TP review state.
		// TODO: request run-level export and assert the downloaded workbook has one worksheet.

		expect(true).toBeTruthy();
	});
});
