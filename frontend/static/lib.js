let map; // global for access in other funcs

// Notification helper (requires a #notification div)
function showNotification(message, isError = false, duration = 4000) {
  const notif = document.getElementById('notification');
  if (!notif) {
    console.warn('Notification element not found');
    return;
  }
  notif.textContent = message;
  notif.style.backgroundColor = isError ? '#e74c3c' : '#27ae60'; // red or green
  notif.classList.add('show');
  clearTimeout(notif.timeoutId);
  notif.timeoutId = setTimeout(() => {
    notif.classList.remove('show');
  }, duration);
}

window.initMap = function () {
  console.log("initMap called");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      map = new google.maps.Map(document.getElementById("map"), {
        zoom: 14,
        center: loc,
      });
      new google.maps.Marker({
        position: loc,
        map: map,
        title: "You are here",
      });

      fetch("/api/parking/spots")
        .then((r) => r.json())
        .then((data) => {
          data.spots.forEach((spot) => {
            const marker = new google.maps.Marker({
              position: { lat: spot.lat, lng: spot.lng },
              map: map,
              title: spot.address,
            });

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

// Variables to hold booking context for modal
let currentBookingSpotId = null;
let currentBookingSpotRate = null;

// Show booking duration modal
function showBookingModal(spotId, rate) {
  currentBookingSpotId = spotId;
  currentBookingSpotRate = rate;
  const modal = document.getElementById('durationModal');
  const input = document.getElementById('durationInput');
  input.value = '';
  modal.classList.add('show');
  input.focus();
}

// Hide booking modal
function hideBookingModal() {
  const modal = document.getElementById('durationModal');
  modal.classList.remove('show');
}

// Confirm booking from modal input
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
        // Optionally refresh map or bookings here
        window.initMap();
      } else if (data.error) {
        showNotification("Booking failed: " + data.error, true);
      } else {
        showNotification("Booking failed, please try again.", true);
      }
    })
    .catch(() => showNotification("Booking failed, please try again.", true));
}

// Override old book function to open modal
window.book = function (id, rate) {
  showBookingModal(id, rate);
};

// Attach modal buttons listeners
document.addEventListener('DOMContentLoaded', () => {
  const confirmBtn = document.getElementById('confirmDurationBtn');
  const cancelBtn = document.getElementById('cancelDurationBtn');

  confirmBtn.addEventListener('click', confirmBooking);
  cancelBtn.addEventListener('click', hideBookingModal);
});

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

// Cancel booking by booking id
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
        loadBookings();  // refresh bookings list
        window.initMap(); // refresh map markers & availability
      } else {
        const data = await res.json();
        showNotification("Cancel failed: " + (data.error || "Unknown error"), true);
      }
    })
    .catch(() => showNotification("Cancel request failed due to network error.", true));
};
