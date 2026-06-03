/**
 * Kadoya Catalogue JavaScript
 * Handles AJAX filtering, search and gallery interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    initFilters();
    initGallery();
    initAddToCart();
});

/**
 * Initialize Category and Sort filters with AJAX
 */
function initFilters() {
    const grid = document.getElementById('products-grid');
    if (!grid) return;

    // Listen for category chip clicks
    document.querySelectorAll('.chip[data-filter]').forEach(chip => {
        chip.addEventListener('click', (e) => {
            e.preventDefault();
            const category = chip.dataset.filter;
            const params = { category: category };
            if (category === 'all') params.category = '';
            
            // UI state
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            
            applyFilters(params);
        });
    });

    // Listen for Sort changes
    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', () => {
            applyFilters({ sort: sortSelect.value });
        });
    }

    // Search bar interaction
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const query = searchForm.querySelector('input').value;
            applyFilters({ q: query });
        });
    }
}

/**
 * Fetch and replace product grid
 */
async function applyFilters(newParams) {
    const grid = document.getElementById('products-grid');
    const countBadge = document.getElementById('results-count');
    
    const url = new URL(window.location.href);
    Object.entries(newParams).forEach(([k, v]) => {
        if (v === '' || v === null) {
            url.searchParams.delete(k);
        } else {
            url.searchParams.set(k, v);
        }
    });

    // Reset to page 1 on new filter
    url.searchParams.delete('page');

    // Show skeletons
    showSkeletons(grid);

    try {
        const response = await fetch(url.toString(), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (!response.ok) throw new Error('Network error');

        const data = await response.json();
        
        // Update DOM
        grid.innerHTML = data.html;
        if (countBadge) countBadge.textContent = data.count;
        
        // Update URL
        history.pushState({}, '', url.toString());

    } catch (error) {
        console.error('Filter error:', error);
        grid.innerHTML = '<div class="col-12 text-center py-5"><p class="text-danger">Une erreur est survenue lors du chargement des produits.</p></div>';
    }
}

/**
 * Show skeleton loaders during AJAX
 */
function showSkeletons(container) {
    const skeletonCount = 8;
    let html = '';
    for (let i = 0; i < skeletonCount; i++) {
        html += `
            <div class="masonry-item">
                <div class="skeleton-card">
                    <div class="skeleton skeleton-img"></div>
                    <div class="skeleton-body">
                        <div class="skeleton skeleton-line"></div>
                        <div class="skeleton skeleton-line short"></div>
                    </div>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}

/**
 * Product Detail Gallery interaction
 */
function initGallery() {
    const mainImg = document.getElementById('main-product-image');
    const thumbnails = document.querySelectorAll('.thumbnail-item');

    if (!mainImg || thumbnails.length === 0) return;

    thumbnails.forEach(thumb => {
        thumb.addEventListener('click', () => {
            const newSrc = thumb.dataset.full;
            mainImg.src = newSrc;

            // UI state
            thumbnails.forEach(t => t.classList.remove('active'));
            thumb.classList.add('active');
        });
    });
}
/**
 * Add to Cart interaction
 */
function initAddToCart() {
    const addBtn = document.getElementById('add-to-cart-btn');
    if (!addBtn) return;

    addBtn.addEventListener('click', async () => {
        const productId = addBtn.dataset.productId;
        const csrfToken = getCsrfToken();

        if (!productId) return;

        // Button UI state: loading
        const originalText = addBtn.innerHTML;
        addBtn.disabled = true;
        addBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Ajout...`;

        try {
            const response = await fetch('/panier/ajouter/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    product_id: productId,
                    quantity: 1
                })
            });

            let data;
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                // Server returned HTML (error page) – show status for debugging
                const text = await response.text();
                console.error('Non-JSON response:', response.status, text.substring(0, 500));
                throw new Error(`Erreur serveur (${response.status}). Voir la console pour les détails.`);
            }

            if (data.success) {
                // Success UI
                addBtn.classList.replace('btn-kadoya', 'btn-success');
                addBtn.innerHTML = `<i class="bi bi-check-lg me-2"></i>Ajouté !`;
                
                // Update navbar cart badge
                const cartBadge = document.querySelector('.navbar .badge');
                if (cartBadge) {
                    cartBadge.textContent = data.cart_total_items;
                    cartBadge.classList.add('pulse');
                    setTimeout(() => cartBadge.classList.remove('pulse'), 1000);
                }

                // Reset button after 2 seconds
                setTimeout(() => {
                    addBtn.classList.replace('btn-success', 'btn-kadoya');
                    addBtn.innerHTML = originalText;
                    addBtn.disabled = false;
                }, 2000);

            } else {
                throw new Error(data.error || 'Erreur lors de l\'ajout');
            }

        } catch (error) {
            console.error('Cart error:', error);
            // Show error inline rather than alert
            addBtn.classList.remove('btn-kadoya');
            addBtn.classList.add('btn-danger');
            addBtn.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>${error.message}`;
            setTimeout(() => {
                addBtn.classList.replace('btn-danger', 'btn-kadoya');
                addBtn.innerHTML = originalText;
                addBtn.disabled = false;
            }, 4000);
        }
    });
}
