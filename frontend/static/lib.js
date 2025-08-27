/**
 * lib.js - Frontend logic for ParkPing app
 *
 * Responsibilities:
 *  - Initialize Google Maps and show user location
 *  - Fetch and display available parking spots
 *  - Allow users to book parking spots with a duration modal
 *  - Load and manage user bookings (display, cancel, refresh)
 *  - Show notifications for user feedback
 *
 * Dependencies:
 *  - Google Maps JavaScript API
 *  - Backend API endpoints (/api/parking/spots, /api/parking/book, /api/parking/bookings, /api/parking/cancel)
 *  - HTML elements: #map, #notification, #durationModal, #durationInput, #confirmDurationButton, #cancelDurationButton, #bookingResults
 */

let map; // Global reference to the Google Maps instance

/**
 * Show a temporary notification message at the top of the UI
 *
 * @param {string} message - The text message to display
 * @param {boolean} [isError=false] - Whether to show an error or success message
 * @param {number} [duration=4000] - How long the message stays visible (duration is in ms)
 */
function showNotification(message, isError = false, duration = 4000) {
  const notif = document.getElementById('notification');
  if (!notif) {
    console.warn('Notification element not found');
    return;
  }
  notif.textContent = message;
  notif.style.backgroundColor = isError ? '#e74c3c' : '#27ae60';
  notif.classList.add('show');
  clearTimeout(notif.timeoutId);
  notif.timeoutId = setTimeout(() => {
    notif.classList.remove('show');
  }, duration);
}

/**
 * Initialize the Google Map centered on the user's location
 * Fetches available parking spots and adds markers for them
 */
window.initMap = function () {
  console.log("initMap called");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      map = new google.maps.Map(document.getElementById("map"), {
        zoom: 14,
        center: loc,
      });

      // Marker for user’s location
      new google.maps.Marker({
        position: loc,
        map: map,
        title: "You are here",
      });

      // Fetch and display available parking spots
      fetch("/api/parking/spots")
        .then((r) => r.json())
        .then((data) => {
          data.spots.forEach((spot) => {
            const marker = new google.maps.Marker({
              position: { lat: spot.lat, lng: spot.lng },
              map: map,
              title: spot.address,
            });

            // InfoWindow shows details and booking option
            const infoWindow = new google.maps.InfoWindow({
              content: `
                <div>
                  <h6>${spot.address}</h6>
                  <p>$${spot.rate}/hr</p>
                  <p><strong>Organizer:</strong> ${spot.creator_name}</p>
                  <button onclick="book(${spot.id}, ${spot.rate})">Book</button>
                </div>`,
            });

            marker.addListener("click", () => {
              infoWindow.open(map, marker);
            });
          });
        });
    },
    (err) => {
      showNotification("Error getting your location: " + err.message, true);
    }
  );
};

//Booking modal state
let currentBookingSpotId = null;   // Active spot being booked
let currentBookingSpotRate = null; // Rate of the active spot

/**
 * Show the booking modal where the user enters duration
 *
 * @param {number} spotId - ID of the spot to book
 * @param {number} rate - Hourly rate of the spot
 */
function showBookingModal(spotId, rate) {
  currentBookingSpotId = spotId;
  currentBookingSpotRate = rate;
  const modal = document.getElementById('durationModal');
  const input = document.getElementById('durationInput');
  input.value = '';
  modal.classList.add('show');
  input.focus();
}

/** Hide the booking duration modal. */
function hideBookingModal() {
  const modal = document.getElementById('durationModal');
  modal.classList.remove('show');
}

/**
 * Confirm the booking with user-entered duration
 * Sends request to backend and refreshes map on success
 */
function confirmBooking() {
  const input = document.getElementById('durationInput');
  const hours = Number(input.value);
  if (!hours || hours <= 0 || isNaN(hours)) {
    alert("Please enter a valid positive number of hours.");
    input.focus();
    return;
  }
  hideBookingModal();

  fetch("/api/parking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spot_id: currentBookingSpotId, hours }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.cost !== undefined) {
        showNotification("Booked. Cost: $" + data.cost);
        window.initMap(); // Refresh map markers
      } else if (data.error) {
        showNotification("Booking failed: " + data.error, true);
      } else {
        showNotification("Booking failed, please try again.", true);
      }
    })
    .catch(() => showNotification("Booking failed, please try again.", true));
}

/**
 * Open booking modal when user clicks "Book" button on a spot
 * Overrides the old book() function
 *
 * @param {number} id - ID of the spot
 * @param {number} rate - Hourly rate
 */
window.book = function (id, rate) {
  showBookingModal(id, rate);
};

// Attach modal button listeners on page load
document.addEventListener('DOMContentLoaded', () => {
  const confirmBtn = document.getElementById('confirmDurationBtn');
  const cancelBtn = document.getElementById('cancelDurationBtn');
  confirmBtn.addEventListener('click', confirmBooking);
  cancelBtn.addEventListener('click', hideBookingModal);
});

/**
 * Load all bookings of the current user and display them in the DOM
 * Adds blue markers on the map for each booking
 */
window.loadBookings = function () {
  fetch("/api/parking/bookings")
    .then((r) => r.json())
    .then((data) => {
      const list = document.getElementById("bookingResults");
      list.innerHTML = "<h3>Your Bookings:</h3>";
      if (!data.bookings.length) {
        list.innerHTML += "<p>No bookings found.</p>";
        return;
      }

      list.innerHTML += '<div style="display: flex; flex-direction: column; gap: 12px;">';

      data.bookings.forEach((b) => {
        list.innerHTML += `
          <div style="border-bottom: 1px solid #ccc; padding-bottom: 8px;">
            <strong>${b.address}</strong><br/>
            From: ${new Date(b.start_time).toLocaleString()}<br/>
            To: ${new Date(b.end_time).toLocaleString()}<br/>
            Cost: $${b.cost}<br/>
            Status: ${b.paid ? "Paid" : "Unpaid"}<br/>
            <button onclick="cancelBooking(${b.id})" style="
              margin-top: 6px;
              background: #e74c3c;
              color: white;
              border: none;
              padding: 6px 12px;
              border-radius: 6px;
              cursor: pointer;
            ">Cancel Booking</button>
          </div>
        `;

        // Blue marker for booked spots
        new google.maps.Marker({
          position: { lat: b.lat, lng: b.lng },
          map: map,
          title: "Your booking: " + b.address,
          icon: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
        });
      });

      list.innerHTML += '</div>';
    })
    .catch(() => showNotification("Failed to load bookings", true));
};

/**
 * Cancel an existing booking
 * Confirms with the user, then calls backend to cancel
 *
 * @param {number} bookingId - ID of the booking to cancel
 */
window.cancelBooking = function (bookingId) {
  if (!confirm("Are you sure you want to cancel this booking?")) return;

  fetch("/api/parking/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ booking_id: bookingId }),
  })
    .then(async (res) => {
      if (res.ok) {
        showNotification("Booking cancelled successfully.");
        loadBookings();   // Refresh bookings list
        window.initMap(); // Refresh map markers
      } else {
        const data = await res.json();
        showNotification("Cancel failed: " + (data.error || "Unknown error"), true);
      }
    })
    .catch(() => showNotification("Cancel request failed due to network error.", true));
};
