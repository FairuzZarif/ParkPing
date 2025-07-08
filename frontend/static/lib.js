let map; // Make it global so other functions can access

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
      alert("Error getting your location: " + err.message);
    }
  );
};

window.book = function (id, rate) {
  const hours = prompt("Enter hours:");
  if (!hours || isNaN(hours) || hours <= 0) {
    alert("Please enter a valid number of hours.");
    return;
  }
  fetch("/api/parking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spot_id: id, hours }),
  })
    .then((r) => r.json())
    .then((data) => {
      alert("Booked. Cost: $" + data.cost);
    })
    .catch(() => alert("Booking failed, please try again."));
};

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

      data.bookings.forEach((b) => {
        list.innerHTML += `
          <div style="margin-bottom: 10px;">
            <strong>${b.address}</strong><br/>
            From: ${new Date(b.start_time).toLocaleString()}<br/>
            To: ${new Date(b.end_time).toLocaleString()}<br/>
            Cost: $${b.cost}<br/>
            Status: ${b.paid ? "Paid" : "Unpaid"}
          </div>
        `;

        new google.maps.Marker({
          position: { lat: b.lat, lng: b.lng },
          map: map,
          title: "Your booking: " + b.address,
          icon: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
        });
      });
    })
    .catch(() => alert("Failed to load bookings"));
};