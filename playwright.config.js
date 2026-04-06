const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
	testDir: './tests/e2e',
	timeout: 3 * 60 * 1000,
	expect: {
		timeout: 30 * 1000,
	},
	fullyParallel: false,
	retries: 0,
	reporter: 'list',
	use: {
		baseURL: process.env.HUBGH_BASE_URL || 'http://localhost',
		headless: process.env.HUBGH_E2E_HEADLESS === '0' ? false : true,
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		video: 'retain-on-failure',
	},
	projects: [
		{
			name: 'firefox',
			use: {
				...devices['Desktop Firefox'],
			},
		},
	],
});
