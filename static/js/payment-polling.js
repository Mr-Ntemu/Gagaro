/**
 * static/js/payment-polling.js
 */

const POLL_INTERVAL_MS = 5000;    // toutes les 5 secondes
const MAX_DURATION_MS  = 5 * 60 * 1000;  // 5 minutes max
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

    // Mise à jour timer
    updateTimer(MAX_DURATION_MS - elapsed);

    try {
        const response = await fetch(pollUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await response.json();

        if (data.status === 'success' || data.order_status === 'paid') {
            clearInterval(pollInterval);
            showSuccessAnimation();
            setTimeout(() => {
                window.location.href = data.redirect_url || successUrl;
            }, 1500);

        } else if (data.status === 'failed') {
            clearInterval(pollInterval);
            window.location.href = failedUrl;
        }
        // Si 'pending' → continuer à poller

    } catch (error) {
        console.error('Erreur polling :', error);
    }
}

function updateTimer(remainingMs) {
    const minutes = Math.floor(remainingMs / 60000);
    const seconds = Math.floor((remainingMs % 60000) / 1000);
    const timerText = document.getElementById('timer-text');
    if (timerText) {
        timerText.textContent = `Expire dans ${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    const pct = (remainingMs / MAX_DURATION_MS) * 100;
    const timerFill = document.getElementById('timer-fill');
    if (timerFill) {
        timerFill.style.width = `${pct}%`;
    }
}

function showSuccessAnimation() {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.innerHTML = `
            <div class="success-icon text-success fs-3">✅</div>
            <span class="text-success fw-bold">Paiement confirmé ! Redirection...</span>
        `;
    }
}

function showTimeoutMessage() {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.innerHTML = `
            <div class="text-warning fs-3">⚠️</div>
            <span class="text-warning fw-bold">Délai expiré. Veuillez réessayer.</span>
        `;
    }
    setTimeout(() => {
        window.location.href = failedUrl;
    }, 3000);
}

// Démarrer le polling
pollInterval = setInterval(checkPaymentStatus, POLL_INTERVAL_MS);
checkPaymentStatus(); // premier appel immédiat
