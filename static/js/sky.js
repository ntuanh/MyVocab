// File: static/js/sky.js
// Live sky: fetches the time of day (sunrise, sunset, the place's clock) and the
// current weather for the chosen place from Open-Meteo -- free, no API key --
// and runs the place picker in the top bar. theme.js applies the result.

(function () {
    const sky = window.MyVocabSky;
    if (!sky) return;

    const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';
    const GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search';
    // A reading this fresh is reused across page loads instead of asking again.
    const REFRESH_MS = 15 * 60 * 1000;
    const SEARCH_DELAY_MS = 350;

    const PLACES = [
        { name: 'Hà Nội', country: 'Vietnam', lat: 21.0285, lon: 105.8542 },
        { name: 'TP. Hồ Chí Minh', country: 'Vietnam', lat: 10.8231, lon: 106.6297 },
        { name: 'Đà Nẵng', country: 'Vietnam', lat: 16.0544, lon: 108.2022 },
        { name: 'Hải Phòng', country: 'Vietnam', lat: 20.8449, lon: 106.6881 },
        { name: 'Huế', country: 'Vietnam', lat: 16.4637, lon: 107.5909 },
        { name: 'Cần Thơ', country: 'Vietnam', lat: 10.0452, lon: 105.7469 },
        { name: 'Nha Trang', country: 'Vietnam', lat: 12.2388, lon: 109.1967 },
        { name: 'Đà Lạt', country: 'Vietnam', lat: 11.9404, lon: 108.4583 },
        { name: 'Hạ Long', country: 'Vietnam', lat: 20.9599, lon: 107.0425 },
        { name: 'Sa Pa', country: 'Vietnam', lat: 22.3364, lon: 103.8438 },
        { name: 'Vinh', country: 'Vietnam', lat: 18.6796, lon: 105.6813 },
        { name: 'Quy Nhơn', country: 'Vietnam', lat: 13.782, lon: 109.2197 },
        { name: 'Phú Quốc', country: 'Vietnam', lat: 10.2899, lon: 103.984 },
        { name: 'Tokyo', country: 'Japan', lat: 35.6762, lon: 139.6503 },
        { name: 'Seoul', country: 'South Korea', lat: 37.5665, lon: 126.978 },
        { name: 'Singapore', country: 'Singapore', lat: 1.3521, lon: 103.8198 },
        { name: 'Bangkok', country: 'Thailand', lat: 13.7563, lon: 100.5018 },
        { name: 'Sydney', country: 'Australia', lat: -33.8688, lon: 151.2093 },
        { name: 'Dubai', country: 'United Arab Emirates', lat: 25.2048, lon: 55.2708 },
        { name: 'Moscow', country: 'Russia', lat: 55.7558, lon: 37.6173 },
        { name: 'Paris', country: 'France', lat: 48.8566, lon: 2.3522 },
        { name: 'London', country: 'United Kingdom', lat: 51.5074, lon: -0.1278 },
        { name: 'Reykjavík', country: 'Iceland', lat: 64.1466, lon: -21.9426 },
        { name: 'New York', country: 'United States', lat: 40.7128, lon: -74.006 },
        { name: 'Los Angeles', country: 'United States', lat: 34.0522, lon: -118.2437 },
    ];

    // WMO weather codes, as Open-Meteo reports them: a label for people and
    // the look the stylesheet draws.
    const CODES = {
        0: ['Clear sky', 'clear'], 1: ['Mainly clear', 'clear'], 2: ['Partly cloudy', 'partly'],
        3: ['Overcast', 'cloudy'], 45: ['Fog', 'fog'], 48: ['Freezing fog', 'fog'],
        51: ['Light drizzle', 'drizzle'], 53: ['Drizzle', 'drizzle'], 55: ['Heavy drizzle', 'drizzle'],
        56: ['Freezing drizzle', 'drizzle'], 57: ['Freezing drizzle', 'drizzle'],
        61: ['Light rain', 'rain'], 63: ['Rain', 'rain'], 65: ['Heavy rain', 'rain'],
        66: ['Freezing rain', 'rain'], 67: ['Freezing rain', 'rain'],
        71: ['Light snow', 'snow'], 73: ['Snow', 'snow'], 75: ['Heavy snow', 'snow'], 77: ['Snow grains', 'snow'],
        80: ['Rain showers', 'rain'], 81: ['Rain showers', 'rain'], 82: ['Violent rain showers', 'rain'],
        85: ['Snow showers', 'snow'], 86: ['Heavy snow showers', 'snow'],
        95: ['Thunderstorm', 'storm'], 96: ['Thunderstorm with hail', 'storm'], 99: ['Thunderstorm with hail', 'storm'],
    };

    const ICONS = {
        clear: ['fa-sun', 'fa-moon'], partly: ['fa-cloud-sun', 'fa-cloud-moon'], cloudy: ['fa-cloud', 'fa-cloud'],
        fog: ['fa-smog', 'fa-smog'], drizzle: ['fa-cloud-rain', 'fa-cloud-rain'],
        rain: ['fa-cloud-showers-heavy', 'fa-cloud-showers-heavy'], storm: ['fa-bolt', 'fa-bolt'],
        snow: ['fa-snowflake', 'fa-snowflake'],
    };

    // --- 1. ELEMENTS ---
    const picker = document.getElementById('sky-picker');
    if (!picker) return;
    const button = document.getElementById('sky-button');
    const buttonIcon = document.getElementById('sky-button-icon');
    const buttonPlace = document.getElementById('sky-button-place');
    const buttonTemp = document.getElementById('sky-button-temp');
    const panel = document.getElementById('sky-panel');
    const nowIcon = document.getElementById('sky-now-icon');
    const nowMain = document.getElementById('sky-now-main');
    const nowDetail = document.getElementById('sky-now-detail');
    const statusEl = document.getElementById('sky-status');
    const searchInput = document.getElementById('sky-search');
    const placeList = document.getElementById('sky-places');
    const lookButtons = Array.from(document.querySelectorAll('#sky-looks [data-look]'));
    const effectsBox = document.getElementById('sky-effects');

    let searchTimer = null;
    let searchRun = 0;

    // --- 2. HELPERS ---

    function currentPlace() {
        return sky.prefs.place || PLACES[0];
    }

    function placeKey(place) {
        return `${place.lat.toFixed(3)},${place.lon.toFixed(3)}`;
    }

    function clock(minutes) {
        return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
    }

    // "2026-10-04T17:41" -> minutes since midnight, already in the place's time.
    function minutesOf(isoTime) {
        if (typeof isoTime !== 'string' || isoTime.length < 16) return null;
        const [hours, minutes] = isoTime.slice(11, 16).split(':').map(Number);
        return hours * 60 + minutes;
    }

    function setIcon(element, iconClass) {
        element.className = `fas ${iconClass}`;
    }

    function setStatus(message) {
        statusEl.textContent = message || '';
        statusEl.hidden = !message;
    }

    // --- 3. WEATHER ---

    async function fetchReading(place) {
        const params = new URLSearchParams({
            latitude: place.lat, longitude: place.lon,
            current: 'temperature_2m,weather_code,is_day',
            daily: 'sunrise,sunset', timezone: 'auto', forecast_days: 1,
        });
        const response = await fetch(`${FORECAST_URL}?${params}`);
        if (!response.ok) throw new Error(`The weather service answered ${response.status}.`);
        const data = await response.json();
        const current = data.current || {};
        const [label, weather] = CODES[current.weather_code] || ['Unknown weather', 'clear'];
        const sunrise = minutesOf(data.daily && data.daily.sunrise && data.daily.sunrise[0]);
        const sunset = minutesOf(data.daily && data.daily.sunset && data.daily.sunset[0]);
        const polar = sunrise === null || sunset === null || sunrise === sunset;
        return {
            place: placeKey(place),
            fetchedAt: Date.now(),
            utcOffset: Number(data.utc_offset_seconds) || 0,
            sunrise: polar ? null : sunrise,
            sunset: polar ? null : sunset,
            isDay: current.is_day === 1,
            temperature: Math.round(current.temperature_2m),
            label,
            weather,
        };
    }

    async function refresh(force = false) {
        const place = currentPlace();
        const reading = sky.reading;
        const samePlace = reading && reading.place === placeKey(place);
        if (!force && samePlace && Date.now() - reading.fetchedAt < REFRESH_MS) {
            update();
            return;
        }
        try {
            sky.saveReading(await fetchReading(place));
            setStatus('');
        } catch (error) {
            // A reading for this place, however old, beats none; one for another
            // place would show the wrong sky, so fall back to the device clock.
            if (!samePlace) sky.saveReading(null);
            setStatus("Couldn't reach the weather service, so the look follows this device's clock for now.");
        }
        update();
    }

    // --- 4. RENDERING ---

    function update() {
        sky.apply();
        const place = currentPlace();
        const reading = sky.reading && sky.reading.place === placeKey(place) ? sky.reading : null;
        const night = sky.liveScene() === 'night';

        buttonPlace.textContent = place.name;
        if (reading) {
            const icon = ICONS[reading.weather][night ? 1 : 0];
            setIcon(buttonIcon, icon);
            setIcon(nowIcon, icon);
            buttonTemp.textContent = `${reading.temperature}°`;
            const time = clock(sky.placeMinutes(reading.utcOffset));
            nowMain.textContent = `${time} · ${reading.temperature}°C · ${reading.label}`;
            nowDetail.textContent = reading.sunrise == null
                ? `in ${place.name}`
                : `in ${place.name} · Sunrise ${clock(reading.sunrise)} · Sunset ${clock(reading.sunset)}`;
        } else {
            setIcon(buttonIcon, night ? 'fa-moon' : 'fa-sun');
            setIcon(nowIcon, night ? 'fa-moon' : 'fa-sun');
            buttonTemp.textContent = '';
            nowMain.textContent = `Weather for ${place.name} is loading...`;
            nowDetail.textContent = '';
        }
        button.setAttribute('aria-label', reading
            ? `${place.name}, ${reading.temperature} degrees, ${reading.label}. Change place or look`
            : `${place.name}. Change place or look`);

        lookButtons.forEach(b => b.setAttribute('aria-checked', String(b.dataset.look === sky.prefs.look)));
        effectsBox.checked = sky.prefs.effects;
        markSelectedPlace();
    }

    function placeOption(place, iconClass, onPick) {
        const item = document.createElement('li');
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'sky-place';
        option.setAttribute('role', 'option');
        if (place) option.dataset.key = placeKey(place);
        const icon = document.createElement('i');
        icon.className = `fas ${iconClass}`;
        const name = document.createElement('span');
        name.textContent = place ? place.name : 'Use my location';
        option.append(icon, name);
        if (place && place.country) {
            const country = document.createElement('small');
            country.textContent = place.country;
            option.append(country);
        }
        option.addEventListener('click', onPick);
        item.append(option);
        return item;
    }

    function choosePlace(place) {
        sky.prefs.place = place;
        sky.savePrefs();
        searchInput.value = '';
        showPlaces(PLACES);
        refresh(true);
    }

    function showPlaces(places, note) {
        placeList.replaceChildren();
        if (!note && places === PLACES) {
            placeList.append(placeOption(null, 'fa-location-arrow', useMyLocation));
        }
        if (note) {
            const item = document.createElement('li');
            item.className = 'sky-places-note';
            item.textContent = note;
            placeList.append(item);
        }
        places.forEach(place => placeList.append(placeOption(place, 'fa-map-marker-alt', () => choosePlace(place))));
        markSelectedPlace();
    }

    function markSelectedPlace() {
        const key = placeKey(currentPlace());
        placeList.querySelectorAll('.sky-place').forEach(option => {
            option.setAttribute('aria-selected', String(option.dataset.key === key));
        });
    }

    // --- 5. PLACE SEARCH & MY LOCATION ---

    async function search(query) {
        const run = ++searchRun;
        try {
            const params = new URLSearchParams({ name: query, count: 10, language: 'en' });
            const response = await fetch(`${GEOCODE_URL}?${params}`);
            const data = await response.json();
            if (run !== searchRun) return;  // a newer search has started
            const places = (data.results || []).map(r => ({
                name: r.name,
                country: [r.admin1, r.country].filter(Boolean).join(', '),
                lat: r.latitude,
                lon: r.longitude,
            }));
            showPlaces(places, places.length ? null : `No places found for "${query}".`);
        } catch (error) {
            if (run === searchRun) showPlaces([], 'Search is unavailable right now.');
        }
    }

    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        const query = searchInput.value.trim();
        if (query.length < 2) {
            searchRun++;
            showPlaces(PLACES);
            return;
        }
        searchTimer = setTimeout(() => search(query), SEARCH_DELAY_MS);
    });

    function useMyLocation() {
        if (!navigator.geolocation) {
            setStatus("This browser can't share its location.");
            return;
        }
        setStatus('Finding your location...');
        navigator.geolocation.getCurrentPosition(
            position => {
                setStatus('');
                choosePlace({
                    name: 'My location', country: '',
                    lat: Number(position.coords.latitude.toFixed(4)),
                    lon: Number(position.coords.longitude.toFixed(4)),
                });
            },
            () => setStatus('Location was not shared. Pick a city from the list instead.'),
            { timeout: 10000, maximumAge: 30 * 60 * 1000 },
        );
    }

    // --- 6. PANEL ---

    function openPanel() {
        panel.hidden = false;
        button.setAttribute('aria-expanded', 'true');
        searchInput.focus();
    }

    function closePanel() {
        panel.hidden = true;
        button.setAttribute('aria-expanded', 'false');
    }

    button.addEventListener('click', () => (panel.hidden ? openPanel() : closePanel()));
    // composedPath, not contains(): picking a place redraws the list, so by the
    // time this runs the clicked row is no longer in the document.
    document.addEventListener('click', (event) => {
        if (!panel.hidden && !event.composedPath().includes(picker)) closePanel();
    });
    panel.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closePanel();
            button.focus();
        }
    });

    lookButtons.forEach(b => b.addEventListener('click', () => {
        sky.prefs.look = b.dataset.look;
        sky.savePrefs();
        update();
    }));

    effectsBox.addEventListener('change', () => {
        sky.prefs.effects = effectsBox.checked;
        sky.savePrefs();
        update();
    });

    // --- 7. START ---
    showPlaces(PLACES);
    refresh();
    // The scene follows the place's clock minute by minute; the weather itself
    // is asked for again every REFRESH_MS.
    setInterval(update, 60 * 1000);
    setInterval(() => refresh(true), REFRESH_MS);
})();
