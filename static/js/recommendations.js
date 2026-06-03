/**
 * Kadoya — Moteur de recommandation côté client
 * Charge les recommandations via AJAX et les injecte dans le DOM.
 */

const RecoConfig = {
  apiUrl:     '/api/reco/',
  anonUrl:    '/api/reco/anonyme/',
  trackUrl:   '/api/reco/track/',
  isAuth:     document.body.dataset.userAuth === 'true',
};


// ── Chargement des recommandations ────────────────────────────────────────────

async function loadRecommendations({
  containerId,
  context   = 'global',
  limit     = 8,
  excludeIds = [],
  categoryIds = [],
}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  // Construire l'URL
  const url    = new URL(
    RecoConfig.isAuth ? RecoConfig.apiUrl : RecoConfig.anonUrl,
    window.location.origin
  );
  url.searchParams.set('context', context);
  url.searchParams.set('limit', limit);
  if (excludeIds.length)   url.searchParams.set('exclude', excludeIds.join(','));
  if (categoryIds.length)  url.searchParams.set('categories', categoryIds.join(','));

  try {
    const res  = await fetch(url.toString(), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    const data = await res.json();

    container.classList.remove('loading');

    if (!data.products || data.products.length === 0) {
      container.innerHTML = `
        <p class="reco-empty">Aucune recommandation disponible pour l'instant.</p>
      `;
      return;
    }

    container.innerHTML = data.products.map(renderRecoCard).join('');
    initRecoCardInteractions(container);

  } catch (err) {
    console.warn('[Reco] Erreur chargement :', err);
    container.classList.remove('loading');
    container.innerHTML = '';
  }
}


// ── Rendu d'une carte recommandée ─────────────────────────────────────────────

function renderRecoCard(product) {
  const imgHtml = product.cover_url
    ? `<img src="${product.cover_url}" alt="${product.title}"
             class="reco-card-img" loading="lazy">`
    : `<div class="reco-card-img-placeholder">
         <i class="bi bi-image"></i>
       </div>`;

  const discountBadge = product.has_discount && product.discount_pct
    ? `<span class="reco-badge-discount">-${product.discount_pct}%</span>`
    : '';

  const customBadge = product.is_customizable
    ? `<span class="reco-badge-custom" title="Personnalisable">✏️</span>`
    : '';

  return `
    <article class="reco-card" data-product-id="${product.pk}">
      <a href="${product.detail_url}" class="reco-card-link">
        <div class="reco-card-image">
          ${imgHtml}
          ${discountBadge}
          ${customBadge}
          <div class="reco-card-overlay">
            <span class="btn btn-sm btn-light">Voir</span>
          </div>
        </div>
        <div class="reco-card-body">
          <span class="reco-card-category">${product.category}</span>
          <h4 class="reco-card-title">${product.title}</h4>
          <p class="reco-card-price">${formatPrice(product.price)} FCFA</p>
        </div>
      </a>
    </article>
  `;
}

function formatPrice(price) {
  return parseFloat(price).toLocaleString('fr-FR');
}


// ── Interactions avec les cartes recommandées ─────────────────────────────────

function initRecoCardInteractions(container) {
  // Tracker les clics (comptent comme des vues)
  container.querySelectorAll('.reco-card').forEach(card => {
    card.addEventListener('click', () => {
      const productId = card.dataset.productId;
      if (RecoConfig.isAuth && productId) {
        trackBehavior(productId, 'view');
      }
    });
  });
}


// ── Tracking comportemental ───────────────────────────────────────────────────

async function trackBehavior(productId, eventType) {
  if (!RecoConfig.isAuth) return;
  try {
    await fetch(RecoConfig.trackUrl, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCsrfToken(),
      },
      body: JSON.stringify({
        product_id: parseInt(productId),
        event_type: eventType,
      }),
    });
  } catch (err) {
    // Fail silently — ne jamais bloquer l'UX pour du tracking
    console.debug('[Reco] Track échoué :', err);
  }
}

// Tracker les vues longues (> 5 secondes sur la page détail)
function initDetailPageTracking(productId) {
  if (!RecoConfig.isAuth || !productId) return;
  let tracked = false;
  setTimeout(() => {
    if (!tracked) {
      trackBehavior(productId, 'view');
      tracked = true;
    }
  }, 5000);
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

// ── Initialisation par page ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Homepage
  if (document.getElementById('reco-home-strip')) {
    loadRecommendations({
      containerId: 'reco-home-strip',
      context:     'home',
      limit:       8,
    });
  }

  // Page produit (récupère le product_id et la catégorie depuis data attributes)
  const recoProductStrip = document.getElementById('reco-product-strip');
  if (recoProductStrip) {
    const productId  = recoProductStrip.dataset.currentProduct;
    const categoryId = recoProductStrip.dataset.currentCategory;
    loadRecommendations({
      containerId: 'reco-product-strip',
      context:     'product',
      limit:       4,
      excludeIds:  productId ? [parseInt(productId)] : [],
      categoryIds: categoryId ? [parseInt(categoryId)] : [],
    });
    // Tracking vue longue
    initDetailPageTracking(productId);
  }

  // Page panier
  if (document.getElementById('reco-cart-strip')) {
    // Récupérer les IDs des articles dans le panier depuis les data-attributes
    const cartItems  = document.querySelectorAll('[data-cart-product-id]');
    const cartIds    = [...cartItems].map(el =>
                         parseInt(el.dataset.cartProductId)
                       ).filter(Boolean);
    loadRecommendations({
      containerId: 'reco-cart-strip',
      context:     'cart',
      limit:       4,
      excludeIds:  cartIds,
    });
  }

});
