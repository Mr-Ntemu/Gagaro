/**
 * static/js/payment-polling.js
 */

const POLL_INTERVAL_MS = 5000;
const MAX_DURATION_MS  = 5 * 60 * 1000;  // 5 minutes
let   startTime        = Date.now();
let   pollInterval     = null;

async function checkPaymentStatus() {
    const elapsed = Date.now() - startTime;

    // Timeout côté client après 5 minutes
    if (elapsed >= MAX_DURATION_MS) {
        clearInterval(pollInterval);
        showTimeoutMessage();
        return;
    }

    updateTimer(MAX_DURATION_MS - elapsed);

    try {
        const response = await fetch(pollUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await response.json();

        // Normalise le statut en minuscules pour comparaison uniforme
        // (Django renvoie 'success'/'failed', SharePay renvoie 'SUCCESS'/'FAILED')
        const status      = (data.status || '').toLowerCase();
        const orderStatus = (data.order_status || '').toLowerCase();

        if (status === 'success' || orderStatus === 'paid') {
            // ✅ Paiement confirmé
            clearInterval(pollInterval);
            showSuccessAnimation();
            setTimeout(() => {
                window.location.href = data.redirect_url || successUrl;
            }, 1500);

        } else if (status === 'failed' || status === 'cancelled') {
            // ❌ Paiement échoué ou annulé
            clearInterval(pollInterval);
            showFailedMessage();
            setTimeout(() => {
                window.location.href = failedUrl;
            }, 2000);

        } else if (status === 'processing') {
            // ⏳ Charge directe en cours — notification envoyée au téléphone
            showProcessingMessage();
            // Continue à poller

        }
        // Si 'pending' → continuer à poller sans rien afficher de spécial

    } catch (error) {
        console.error('Erreur polling :', error);
    }
}

function updateTimer(remainingMs) {
    const minutes = Math.floor(remainingMs / 60000);
    const seconds = Math.floor((remainingMs % 60000) / 1000);

    const timerText = document.getElementById('timer-text');
    if (timerText) {
        timerText.textContent =
            `Expire dans ${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    const pct       = (remainingMs / MAX_DURATION_MS) * 100;
    const timerFill = document.getElementById('timer-fill');
    if (timerFill) {
        timerFill.style.width = `${pct}%`;
    }
}

function showProcessingMessage() {
    const indicator = document.getElementById('status-indicator');
    if (indicator && !indicator.dataset.processing) {
        indicator.dataset.processing = true;
        indicator.innerHTML = `
            <div class="spinner-border text-warning" role="status"
                 style="width:1.5rem; height:1.5rem;"></div>
            <span class="text-warning fw-bold">
                Notification envoyée — confirmez sur votre téléphone
            </span>
        `;
    }
}

function showSuccessAnimation() {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.innerHTML = `
            <div class="text-success fs-3">✅</div>
            <span class="text-success fw-bold">
                Paiement confirmé ! Redirection...
            </span>
        `;
    }
}

function showFailedMessage() {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.innerHTML = `
            <div class="text-danger fs-3">❌</div>
            <span class="text-danger fw-bold">
                Paiement échoué. Redirection...
            </span>
        `;
    }
}

function showTimeoutMessage() {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.innerHTML = `
            <div class="text-warning fs-3">⚠️</div>
            <span class="text-warning fw-bold">
                Délai expiré. Veuillez réessayer.
            </span>
        `;
    }
    setTimeout(() => {
        window.location.href = failedUrl;
    }, 3000);
}

// Démarrer le polling
pollInterval = setInterval(checkPaymentStatus, POLL_INTERVAL_MS);
checkPaymentStatus(); // premier appel immédiat