/**
 * KADOYA - Review System JS
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // === STAR RATING INTERACTIF ===
    const starRadios  = document.querySelectorAll('.star-radio input');
    const starDisplay = document.querySelectorAll('.star-display i');
    const ratingLabel = document.getElementById('rating-label');

    const RATING_LABELS = {
      1: 'Très déçu(e) 😞',
      2: 'Déçu(e) 😕',
      3: 'Correct 😐',
      4: 'Satisfait(e) 😊',
      5: 'Excellent ! 🌟',
    };

    if (starDisplay.length > 0) {
        starDisplay.forEach((star, index) => {
            // Hover
            star.addEventListener('mouseenter', () => highlightStars(index + 1));
            star.addEventListener('mouseleave', () => {
                const selected = getSelectedRating();
                highlightStars(selected);
            });
            // Click
            star.addEventListener('click', () => {
                const radio = document.querySelector(`.star-radio input[value="${index + 1}"]`);
                if (radio) {
                    radio.checked = true;
                    highlightStars(index + 1);
                    if (ratingLabel) {
                        ratingLabel.textContent = RATING_LABELS[index + 1];
                        ratingLabel.className   = `rating-label rating-${index + 1}`;
                    }
                }
            });
        });
    }

    function highlightStars(count) {
        starDisplay.forEach((star, i) => {
            if (i < count) {
                star.className = 'bi bi-star-fill text-warning';
            } else {
                star.className = 'bi bi-star text-muted';
            }
        });
    }

    function getSelectedRating() {
        const checked = document.querySelector('.star-radio input:checked');
        return checked ? parseInt(checked.value) : 0;
    }


    // === PHOTO UPLOAD PREVIEW ===
    document.querySelectorAll('.review-photo-slot').forEach((slot, index) => {
        const input   = slot.querySelector('input[type="file"]');
        const preview = slot.querySelector('.photo-preview');
        const clear   = slot.querySelector('.clear-photo');

        if (input) {
            slot.addEventListener('click', (e) => {
                if (e.target !== clear) input.click();
            });

            input.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const reader = new FileReader();
                reader.onload = (ev) => {
                    preview.innerHTML = `
                        <img src="${ev.target.result}" alt="Aperçu photo ${index + 1}"
                             style="width:100%;height:100%;object-fit:cover;border-radius:8px;">
                    `;
                    clear.classList.remove('d-none');
                    slot.classList.add('has-photo');
                };
                reader.readAsDataURL(file);
            });
        }

        if (clear) {
            clear.addEventListener('click', (e) => {
                e.stopPropagation();
                input.value  = '';
                preview.innerHTML = `
                    <i class="bi bi-camera" style="font-size:1.5rem;color:#ccc;"></i>
                    <small>Photo ${index + 1}</small>
                `;
                clear.classList.add('d-none');
                slot.classList.remove('has-photo');
            });
        }
    });


    // === CHARGEMENT AJAX DES AVIS (Product Detail Page) ===
    const reviewsGrid = document.getElementById('reviews-grid');
    const loadMoreBtn = document.getElementById('load-more-reviews');
    let currentPage   = 1;
    let currentRating = null;

    async function loadReviews(page = 1, rating = null, append = false) {
        if (!window.reviewAjaxUrl) return;

        const url = new URL(window.reviewAjaxUrl, window.location.origin);
        url.searchParams.set('page', page);
        if (rating) url.searchParams.set('rating', rating);

        try {
            const res  = await fetch(url.toString(), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await res.json();

            if (!append) reviewsGrid.innerHTML = '';

            if (data.reviews.length === 0 && !append) {
                reviewsGrid.innerHTML = '<p class="text-center text-muted py-4">Aucun avis correspondant.</p>';
            }

            data.reviews.forEach(review => {
                reviewsGrid.insertAdjacentHTML('beforeend', renderReviewCard(review));
            });

            if (loadMoreBtn) {
                loadMoreBtn.style.display = data.has_next ? 'block' : 'none';
            }

            currentPage = page;
            attachArtisanReplyHandlers(); // Re-attach handlers for new elements
        } catch (error) {
            console.error('Error loading reviews:', error);
        }
    }

    function renderReviewCard(r) {
        const stars = Array.from({length: 5}, (_, i) =>
            `<i class="bi bi-star${i < r.rating ? '-fill text-warning' : ' text-muted'}"></i>`
        ).join('');

        const photos = r.photos.map(p =>
            `<a href="${p.full}" target="_blank" class="review-photo-link">
               <img src="${p.thumb || p.full}" alt="${p.caption || ''}" class="review-photo-thumb">
             </a>`
        ).join('');

        return `
            <article class="review-card">
              <div class="review-header">
                <div class="review-avatar">${r.user_name.substring(0,2).toUpperCase()}</div>
                <div>
                  <p class="review-username mb-0 fw-bold">${r.user_name}</p>
                  <time class="review-date text-muted small">${r.created_at}</time>
                </div>
                <div class="ms-auto">${stars}</div>
              </div>
              ${r.title ? `<h4 class="review-title">${r.title}</h4>` : ''}
              <p class="review-body">${r.body}</p>
              ${photos ? `<div class="review-photos">${photos}</div>` : ''}
              ${r.artisan_reply ? `
                <div class="artisan-reply">
                  <div class="artisan-reply-header mb-1">
                    <i class="bi bi-shop me-1 text-secondary"></i>
                    <strong>Réponse de l'artisan</strong>
                    <time class="text-muted small ms-2">${r.artisan_replied_at}</time>
                  </div>
                  <p class="mb-0">${r.artisan_reply}</p>
                </div>` : ''}
            </article>
        `;
    }

    // Filtres par étoile
    document.querySelectorAll('.rating-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.rating-filter-btn')
                    .forEach(b => b.classList.remove('active', 'btn-primary'));
            document.querySelectorAll('.rating-filter-btn')
                    .forEach(b => b.classList.add('btn-outline-secondary'));
            
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('active', 'btn-primary');
            
            currentRating = btn.dataset.rating || null;
            loadReviews(1, currentRating, false);
        });
    });

    // Bouton "Charger plus"
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', () => {
            loadReviews(currentPage + 1, currentRating, true);
        });
    }

    // Chargement initial
    if (reviewsGrid) loadReviews(1);


    // === RÉPONSE ARTISAN ===
    function attachArtisanReplyHandlers() {
        document.querySelectorAll('.reply-btn').forEach(btn => {
            btn.onclick = () => {
                const id   = btn.dataset.reviewId;
                const form = document.getElementById(`reply-form-${id}`);
                form.classList.toggle('d-none');
            };
        });

        document.querySelectorAll('.cancel-reply').forEach(btn => {
            btn.onclick = () => {
                btn.closest('.reply-form').classList.add('d-none');
            };
        });

        document.querySelectorAll('.submit-reply').forEach(btn => {
            btn.onclick = async () => {
                const id      = btn.dataset.reviewId;
                const form    = btn.closest('.reply-form');
                const text    = form.querySelector('textarea').value.trim();
                const replyUrl = `/avis/${id}/repondre/`;

                if (!text) return;

                try {
                    const res  = await fetch(replyUrl, {
                        method:  'POST',
                        headers: {
                            'Content-Type':  'application/json',
                            'X-CSRFToken':   getCsrfToken(),
                        },
                        body: JSON.stringify({ reply: text }),
                    });
                    const data = await res.json();

                    if (data.success) {
                        const card = form.closest('.review-card');
                        form.insertAdjacentHTML('beforebegin', `
                            <div class="artisan-reply">
                                <div class="artisan-reply-header mb-1">
                                    <i class="bi bi-shop me-1 text-secondary"></i>
                                    <strong>Votre réponse</strong>
                                    <time class="text-muted small ms-2">${data.artisan_replied_at}</time>
                                </div>
                                <p class="mb-0">${data.artisan_reply}</p>
                            </div>
                        `);
                        form.remove();
                        card.querySelector('.reply-btn')?.remove();
                    } else {
                        alert(data.error);
                    }
                } catch (error) {
                    console.error('Error submitting reply:', error);
                }
            };
        });
    }

    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    attachArtisanReplyHandlers();
});
