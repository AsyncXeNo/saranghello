from __future__ import annotations

import time
import asyncio

from apify import Actor, Request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        start_urls = actor_input.get('urls')

        if not start_urls:
            Actor.log.info('No start URLs specified in actor input, exiting...')
            await Actor.exit()

        request_queue = await Actor.open_request_queue()

        for start_url in start_urls:
            url = start_url.get('url')
            Actor.log.info(f'Enqueuing {url} ...')
            new_request = Request.from_url(url)
            await request_queue.add_request(new_request)

        Actor.log.info('Launching Chrome WebDriver...')
        chrome_options = ChromeOptions()

        if Actor.config.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(options=chrome_options)

        data = []

        while request := await request_queue.fetch_next_request():
            url = request.url

            Actor.log.info(f'Scraping {url} ...')

            try:
                await asyncio.to_thread(driver.get, url)

                try:
                    collections = [url.split('collections/')[1].split('/')[0]]
                except IndexError:
                    collections = []

                title = driver.find_element(By.CSS_SELECTOR, '.product-single__title').get_attribute('innerText').strip()

                try:
                    price = float(driver.find_element(By.CSS_SELECTOR, '.product-single__prices .sale-price').get_attribute('innerText').replace('$', '').replace('Rs.', '').replace(',', '').strip())
                except Exception:
                    price = float(driver.find_element(By.CSS_SELECTOR, '.product-single__prices .product__price').get_attribute('innerText').replace('$', '').replace('Rs.', '').replace(',', '').strip())
                
                try:
                    main_image = driver.find_element(By.CSS_SELECTOR, '.product__slide.slick-active img').get_attribute('data-photoswipe-src')
                except Exception:
                    main_image = driver.find_element(By.CSS_SELECTOR, '.product__slide img').get_attribute('data-photoswipe-src')
                if main_image.startswith('//'): 
                    main_image = 'https:' + main_image
                
                image_tags = driver.find_elements(By.CSS_SELECTOR, '.product__slide img')
                images = [image.get_attribute('data-photoswipe-src').replace('_114x144_crop_center', '') for image in image_tags]
                for i in range(len(images)):
                    if images[i].startswith('//'):
                        images[i] = 'https:' + images[i]

                description = driver.find_element(By.CSS_SELECTOR, '.product-single__description').get_attribute('innerText').strip()

                variant_inputs = driver.find_elements(By.CSS_SELECTOR, '.variant-input')
                variant_info = []
                for variant_input in variant_inputs:
                    variant_input.click()
                    time.sleep(1)
                    try:
                        variant_price = float(driver.find_element(By.CSS_SELECTOR, '.product-single__prices .sale-price').get_attribute('innerText').replace('$', '').replace('Rs.', '').replace(',', '').strip())
                    except Exception:
                        variant_price = float(driver.find_element(By.CSS_SELECTOR, '.product-single__prices .product__price').get_attribute('innerText').replace('$', '').replace('Rs.', '').replace(',', '').strip())
                    try:
                        variant_image = driver.find_element(By.CSS_SELECTOR, '.product__slide.slick-active img').get_attribute('data-photoswipe-src')
                    except Exception:
                        variant_image = driver.find_element(By.CSS_SELECTOR, '.product__slide img').get_attribute('data-photoswipe-src')
                    if variant_image.startswith('//'):
                        variant_image = 'https:' + variant_image
                    variant_info.append({
                        'name': variant_input.find_element(By.TAG_NAME, 'input').get_attribute('value'),
                        'price': variant_price,
                        'image': variant_image
                    })

                data.append({
                    'url': url,
                    'title': title,
                    'collections': collections,
                    'price': price,
                    'main_image': main_image,
                    'images': images,
                    'description': description,
                    'variants': variant_info
                })

            except Exception:
                Actor.log.exception(f'Cannot extract data from {url}.')

            finally:
                await request_queue.mark_request_as_handled(request)
        
        driver.quit()

        await Actor.push_data({
            'urls': data
        })
