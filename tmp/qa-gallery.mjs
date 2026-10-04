import { chromium } from './browser-tools/node_modules/playwright-core/index.mjs';

const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--disable-gpu', '--no-first-run', '--no-default-browser-check'],
});

const requests = [];
const consoleErrors = [];
const pageErrors = [];
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});

page.on('request', request => requests.push(request.url()));
page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push(message.text());
});
page.on('pageerror', error => pageErrors.push(error.message));

await page.goto('http://127.0.0.1:4173/index.html', {
  waitUntil: 'load',
  timeout: 120_000,
});
await page.waitForFunction(() => document.querySelectorAll('#projectGrid .project').length === 16);

const projects = page.locator('#projectGrid .project');
await projects.first().scrollIntoViewIfNeeded();
await page.waitForTimeout(900);

const desktopState = await page.evaluate(() => ({
  cardCount: document.querySelectorAll('#projectGrid .project').length,
  titles: [...document.querySelectorAll('.project-title')].map(element => element.textContent.trim()),
  loadedCovers: [...document.querySelectorAll('.project-cover')]
    .filter(image => image.complete && image.naturalWidth > 0).length,
  dialogCount: document.querySelectorAll('#galleryDialog').length,
  pdfReferences: document.querySelectorAll('[href$=".pdf" i],[src$=".pdf" i]').length,
  visibleRevealCount: [...document.querySelectorAll('.reveal.show')].length,
}));

await page.screenshot({ path: 'tmp/qa-projects-desktop.png' });

await projects.first().click();
await page.locator('#galleryDialog').waitFor({ state: 'visible' });
await page.waitForTimeout(3000);

const desktopGallery = await page.evaluate(() => ({
  open: document.getElementById('galleryDialog').open,
  title: document.getElementById('galleryTitle').textContent.trim(),
  progress: document.getElementById('galleryProgress').textContent.trim(),
  thumbs: document.querySelectorAll('#galleryThumbs .gallery-thumb').length,
  imagePath: document.getElementById('galleryImage').getAttribute('src'),
  imageWidth: document.getElementById('galleryImage').naturalWidth,
  imageHeight: document.getElementById('galleryImage').naturalHeight,
  imageComplete: document.getElementById('galleryImage').complete,
  caption: document.getElementById('galleryCaption').textContent.trim(),
}));

await page.screenshot({ path: 'tmp/qa-gallery-desktop.png' });

await page.keyboard.press('ArrowRight');
await page.waitForFunction(() => document.getElementById('galleryProgress').textContent.includes('02'));
const afterArrow = await page.locator('#galleryProgress').textContent();

await page.keyboard.press('End');
await page.waitForFunction(() => document.getElementById('galleryProgress').textContent.includes('26 / 26'));
const afterEnd = await page.locator('#galleryProgress').textContent();

await page.keyboard.press('Home');
await page.keyboard.press('Escape');
await page.locator('#galleryDialog').waitFor({ state: 'hidden' });
const focusReturned = await page.evaluate(() => document.activeElement?.matches('#projectGrid .project'));

await page.setViewportSize({ width: 390, height: 844 });
await projects.first().scrollIntoViewIfNeeded();
await page.waitForTimeout(500);
await page.screenshot({ path: 'tmp/qa-projects-mobile.png' });

await projects.first().click();
await page.locator('#galleryDialog').waitFor({ state: 'visible' });
await page.waitForTimeout(3000);
const mobileGallery = await page.evaluate(() => {
  const dialog = document.getElementById('galleryDialog').getBoundingClientRect();
  const image = document.getElementById('galleryImage').getBoundingClientRect();
  const back = document.getElementById('galleryClose').getBoundingClientRect();
  return {
    viewport: { width: innerWidth, height: innerHeight },
    dialog: { width: dialog.width, height: dialog.height },
    image: { width: image.width, height: image.height },
    closeTarget: { width: back.width, height: back.height },
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
  };
});
await page.screenshot({ path: 'tmp/qa-gallery-mobile.png' });

await page.locator('#galleryClose').click();
await page.locator('#galleryDialog').waitFor({ state: 'hidden' });

const results = {
  desktopState,
  desktopGallery,
  keyboard: {
    afterArrow: afterArrow.trim(),
    afterEnd: afterEnd.trim(),
    focusReturned,
  },
  mobileGallery,
  requestedPdfCount: requests.filter(url => /\.pdf(?:$|\?)/i.test(url)).length,
  consoleErrors,
  pageErrors,
};

console.log(JSON.stringify(results, null, 2));
await browser.close();
