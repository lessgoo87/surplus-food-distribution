// ===========================
// SMART SURPLUS FOOD REDISTRIBUTION
// JavaScript Enhancement
// ===========================

document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize all features
    initFormValidation();
    initPriceCalculator();
    initSmoothScrolling();
    initSearchEnhancements();
    initAnimations();
    
});

// ===========================
// FORM VALIDATION
// ===========================

function initFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Add loading state to submit button
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '⏳ Processing...';
                
                // Re-enable after 3 seconds (in case of error)
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = submitBtn.dataset.originalText || 'Submit';
                }, 3000);
            }
        });
    });
}

// ===========================
// PRICE CALCULATOR
// ===========================

function initPriceCalculator() {
    const originalPriceInput = document.getElementById('original_price');
    const discountedPriceInput = document.getElementById('price');
    
    if (originalPriceInput && discountedPriceInput) {
        
        function calculateDiscount() {
            const original = parseFloat(originalPriceInput.value) || 0;
            const discounted = parseFloat(discountedPriceInput.value) || 0;
            
            if (original > 0 && discounted > 0) {
                if (discounted < original) {
                    const discount = Math.round(((original - discounted) / original) * 100);
                    showDiscountMessage(discount, true);
                    discountedPriceInput.setCustomValidity('');
                } else if (discounted >= original) {
                    showDiscountMessage(0, false);
                    discountedPriceInput.setCustomValidity('Discounted price must be less than original price');
                }
            } else {
                removeDiscountMessage();
            }
        }
        
        function showDiscountMessage(discount, isValid) {
            let msg = document.getElementById('discount-msg');
            
            if (!msg) {
                msg = document.createElement('small');
                msg.id = 'discount-msg';
                msg.style.marginTop = '8px';
                msg.style.display = 'block';
                msg.style.fontWeight = '600';
                discountedPriceInput.parentElement.appendChild(msg);
            }
            
            if (isValid) {
                msg.style.color = '#10b981';
                msg.innerHTML = `✓ ${discount}% discount! Great savings for customers!`;
            } else {
                msg.style.color = '#ef4444';
                msg.innerHTML = '✗ Discounted price must be lower than original price';
            }
        }
        
        function removeDiscountMessage() {
            const msg = document.getElementById('discount-msg');
            if (msg) msg.remove();
        }
        
        originalPriceInput.addEventListener('input', calculateDiscount);
        discountedPriceInput.addEventListener('input', calculateDiscount);
    }
}

// ===========================
// SMOOTH SCROLLING
// ===========================

function initSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// ===========================
// SEARCH ENHANCEMENTS
// ===========================

function initSearchEnhancements() {
    // Auto-submit search after typing stops
    const searchInputs = document.querySelectorAll('input[type="text"][name="food"], input[type="text"][name="location"]');
    let searchTimeout;
    
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            // Show searching indicator
            const form = this.closest('form');
            if (!form) return;
            
            clearTimeout(searchTimeout);
            
            // Add subtle indication that search will happen
            this.style.borderColor = '#f59e0b';
            
            searchTimeout = setTimeout(() => {
                this.style.borderColor = '';
                // Uncomment below to enable auto-search
                // form.submit();
            }, 1000);
        });
    });
}

// ===========================
// SCROLL ANIMATIONS
// ===========================

function initAnimations() {
    // Fade in elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observe food cards and other elements
    document.querySelectorAll('.food-card, .how-it-works-item, .stat-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// ===========================
// CONTACT VENDOR (WhatsApp)
// ===========================

function contactVendor(contact, foodName) {
    if (!contact || contact === 'None' || contact === '') {
        showNotification('Contact information not available for this vendor', 'error');
        return;
    }
    
    // Clean phone number
    const cleanContact = contact.replace(/\D/g, '');
    
    // Create message
    const message = `Hi! I'm interested in the ${foodName} listed on the Smart Surplus Food Redistribution app.`;
    const whatsappUrl = `https://wa.me/91${cleanContact}?text=${encodeURIComponent(message)}`;
    
    // Open WhatsApp
    window.open(whatsappUrl, '_blank');
}

// ===========================
// NOTIFICATION SYSTEM
// ===========================

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        background: ${type === 'error' ? '#ef4444' : '#10b981'};
        color: white;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
    `;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add notification animations to CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ===========================
// IMAGE PREVIEW FOR UPLOAD
// ===========================

function initImagePreview() {
    const imageInput = document.getElementById('image');
    
    if (imageInput) {
        imageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            
            if (file) {
                // Check file size (max 5MB)
                if (file.size > 5 * 1024 * 1024) {
                    showNotification('Image size should be less than 5MB', 'error');
                    this.value = '';
                    return;
                }
                
                // Show preview
                const reader = new FileReader();
                reader.onload = function(event) {
                    let preview = document.getElementById('image-preview');
                    
                    if (!preview) {
                        preview = document.createElement('img');
                        preview.id = 'image-preview';
                        preview.style.cssText = `
                            max-width: 200px;
                            max-height: 200px;
                            margin-top: 15px;
                            border-radius: 12px;
                            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                        `;
                        imageInput.parentElement.appendChild(preview);
                    }
                    
                    preview.src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }
}

// Initialize image preview
initImagePreview();

// ===========================
// QUANTITY COUNTER
// ===========================

function initQuantityCounter() {
    const quantityInput = document.getElementById('quantity');
    
    if (quantityInput) {
        // Create increment/decrement buttons
        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'display: flex; gap: 10px; align-items: center;';
        
        const decrementBtn = document.createElement('button');
        decrementBtn.type = 'button';
        decrementBtn.textContent = '-';
        decrementBtn.style.cssText = 'width: 40px; height: 40px; padding: 0;';
        
        const incrementBtn = document.createElement('button');
        incrementBtn.type = 'button';
        incrementBtn.textContent = '+';
        incrementBtn.style.cssText = 'width: 40px; height: 40px; padding: 0;';
        
        quantityInput.parentNode.insertBefore(wrapper, quantityInput);
        wrapper.appendChild(decrementBtn);
        wrapper.appendChild(quantityInput);
        wrapper.appendChild(incrementBtn);
        
        quantityInput.style.textAlign = 'center';
        
        decrementBtn.addEventListener('click', () => {
            const current = parseInt(quantityInput.value) || 1;
            if (current > 1) quantityInput.value = current - 1;
        });
        
        incrementBtn.addEventListener('click', () => {
            const current = parseInt(quantityInput.value) || 1;
            quantityInput.value = current + 1;
        });
    }
}

// Initialize quantity counter
initQuantityCounter();

// ===========================
// LIVE SEARCH COUNTER
// ===========================

function updateSearchResults() {
    const foodCards = document.querySelectorAll('.food-card');
    const resultCount = document.querySelector('.result-count');
    
    if (resultCount && foodCards.length > 0) {
        resultCount.textContent = `${foodCards.length} items found`;
    }
}

// Call on page load
updateSearchResults();

console.log('✅ Smart Surplus Food Redistribution System Loaded');