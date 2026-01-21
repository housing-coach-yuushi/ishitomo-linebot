document.addEventListener('DOMContentLoaded', function () {

    /* Before/After Slider */
    // Select all sliders on the page
    const sliders = document.querySelectorAll('.comparison-slider');

    sliders.forEach(slider => {
        const overlay = slider.querySelector('.overlay');
        const overlayImg = overlay ? overlay.querySelector('img') : null;
        const handle = slider.querySelector('.handle');

        if (overlay && handle) {
            let isDragging = false;

            // Fix image width to match container width to prevent zooming effect
            // Use ResizeObserver for more robust handling of layout changes
            const updateImageWidth = () => {
                if (overlayImg) {
                    overlayImg.style.width = `${slider.offsetWidth}px`;
                }
            };

            // Initial call
            updateImageWidth();

            const resizeObserver = new ResizeObserver(entries => {
                for (let entry of entries) {
                    updateImageWidth();
                }
            });

            resizeObserver.observe(slider);

            const moveSlider = (e) => {
                if (!isDragging) return;
                e.preventDefault();

                const rect = slider.getBoundingClientRect();
                let x = (e.type === 'touchmove') ? e.touches[0].clientX : e.clientX;
                let position = ((x - rect.left) / rect.width) * 100;

                if (position < 0) position = 0;
                if (position > 100) position = 100;

                overlay.style.width = `${position}%`;
                handle.style.left = `${position}%`;
            };

            // Start dragging ONLY on handle
            const startDrag = (e) => {
                isDragging = true;
                e.stopPropagation(); // Prevent other events
                e.preventDefault();  // Prevent selection
            };

            handle.addEventListener('mousedown', startDrag);
            handle.addEventListener('touchstart', startDrag);

            // Global move/up events to handle dragging outside the element
            window.addEventListener('mouseup', () => isDragging = false);
            window.addEventListener('touchend', () => isDragging = false);

            window.addEventListener('mousemove', moveSlider);
            window.addEventListener('touchmove', moveSlider);
        }
    });

    // Optional: Log for debugging
    console.log('Homepage script loaded. Found ' + sliders.length + ' sliders.');

    /* Event Tracking for LINE Friend Add Buttons */
    // Track all "LINEで友だち追加" / "無料で試す" buttons
    const trackEvent = (eventName, eventParams = {}) => {
        // Google Analytics 4
        if (typeof gtag !== 'undefined') {
            gtag('event', eventName, eventParams);
            console.log('GA4 Event tracked:', eventName, eventParams);
        }

        // LINE Tag (conversion tracking)
        // TODO: Uncomment and configure when LINE Tag is set up
        // if (typeof _lt !== 'undefined') {
        //     _lt('send', 'cv', {
        //         type: eventName
        //     });
        // }
    };

    // Track clicks on LINE friend add buttons
    const lineButtons = document.querySelectorAll('button');
    lineButtons.forEach(button => {
        const buttonText = button.textContent.trim();

        // Main CTA: "LINEで友だち追加" or "LINEで受け取る"
        if (buttonText.includes('LINE') && (buttonText.includes('友だち') || buttonText.includes('受け取る'))) {
            button.addEventListener('click', function() {
                trackEvent('line_friend_add_click', {
                    'button_location': getButtonLocation(button),
                    'button_text': buttonText
                });

                // TODO: Add actual LINE friend add URL
                // window.open('https://line.me/R/ti/p/@YOUR_LINE_ID', '_blank');
            });
        }

        // Secondary CTA: "無料で試す"
        if (buttonText.includes('無料で試す')) {
            button.addEventListener('click', function() {
                trackEvent('free_trial_click', {
                    'button_location': getButtonLocation(button),
                    'button_text': buttonText
                });
            });
        }

        // Premium CTA: "今すぐ申し込む"
        if (buttonText.includes('今すぐ申し込む')) {
            button.addEventListener('click', function() {
                trackEvent('premium_signup_click', {
                    'button_location': 'pricing_section',
                    'button_text': buttonText
                });
            });
        }
    });

    // Helper function to identify button location
    function getButtonLocation(button) {
        const parent = button.closest('section') || button.closest('header') || button.closest('footer');
        if (!parent) return 'unknown';

        if (parent.tagName === 'HEADER') return 'header';
        if (parent.tagName === 'FOOTER') return 'footer';
        if (parent.id) return parent.id;

        // Try to identify by nearby headings
        const heading = parent.querySelector('h1, h2, h3');
        if (heading) {
            const headingText = heading.textContent.trim().substring(0, 20);
            return headingText.toLowerCase().replace(/\s+/g, '_');
        }

        return 'main_content';
    }

    // Track page scroll depth
    let maxScrollDepth = 0;
    window.addEventListener('scroll', () => {
        const scrollPercent = Math.round((window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100);

        if (scrollPercent > maxScrollDepth) {
            maxScrollDepth = scrollPercent;

            // Track at 25%, 50%, 75%, 100%
            if (scrollPercent >= 25 && scrollPercent < 50 && maxScrollDepth >= 25) {
                trackEvent('scroll_depth', { 'depth': 25 });
            } else if (scrollPercent >= 50 && scrollPercent < 75 && maxScrollDepth >= 50) {
                trackEvent('scroll_depth', { 'depth': 50 });
            } else if (scrollPercent >= 75 && scrollPercent < 100 && maxScrollDepth >= 75) {
                trackEvent('scroll_depth', { 'depth': 75 });
            } else if (scrollPercent >= 100) {
                trackEvent('scroll_depth', { 'depth': 100 });
            }
        }
    });

    console.log('Event tracking initialized');
});
