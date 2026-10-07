// File: static/js/theme.js
// Puts the right sky on the page before its first paint: the time of day
// (morning, evening or night) and the weather at the chosen place. sky.js
// fetches fresh weather and draws the place picker; this file only applies
// what is already known, so a page never flashes the wrong sky while loading.

(function () {
    const root = document.documentElement;
    const PREFS_KEY = 'myvocab-sky';
    const READING_KEY = 'myvocab-sky-reading';

    const LOOKS = ['auto', 'morning', 'evening', 'night'];
    const WEATHERS = ['clear', 'partly', 'cloudy', 'fog', 'drizzle', 'rain', 'storm', 'snow'];

    // Until the weather service has answered once, the scene follows this
    // device's clock: the hour (0-23) each scene starts at.
    const SCHEDULE = [
        { from: 0, scene: 'night' },
        { from: 5, scene: 'morning' },
        { from: 17, scene: 'evening' },
        { from: 20, scene: 'night' },
    ];

    // Evening is the golden hour: from 90 minutes before sunset until 40 after.
    const EVENING_BEFORE_SUNSET = 90;
    const EVENING_AFTER_SUNSET = 40;

    // Storage can throw in a private window or with site data blocked; the
    // page then follows the clock and remembers nothing.
    function read(key) {
        try {
            return JSON.parse(localStorage.getItem(key));
        } catch (error) {
            return null;
        }
    }

    function write(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) { /* not remembered */ }
    }

    function validPlace(place) {
        return Boolean(place) && typeof place.name === 'string'
            && Number.isFinite(place.lat) && Number.isFinite(place.lon);
    }

    function loadPrefs() {
        const saved = read(PREFS_KEY) || {};
        return {
            look: LOOKS.includes(saved.look) ? saved.look : 'auto',
            effects: saved.effects !== false,
            place: validPlace(saved.place) ? saved.place : null,
        };
    }

    function loadReading() {
        const saved = read(READING_KEY);
        return saved && WEATHERS.includes(saved.weather) && Number.isFinite(saved.utcOffset) ? saved : null;
    }

    // Minutes since midnight at the place, worked out from its UTC offset so it
    // is right whatever time zone this device is in.
    function placeMinutes(utcOffsetSeconds, now = new Date()) {
        const utc = now.getUTCHours() * 60 + now.getUTCMinutes();
        return (((utc + Math.round(utcOffsetSeconds / 60)) % 1440) + 1440) % 1440;
    }

    function sceneFromSun(minutes, sunrise, sunset) {
        if (minutes < sunrise || minutes >= sunset + EVENING_AFTER_SUNSET) return 'night';
        if (minutes >= sunset - EVENING_BEFORE_SUNSET) return 'evening';
        return 'morning';
    }

    function sceneFromClock(hour) {
        return SCHEDULE.filter(step => hour >= step.from).pop().scene;
    }

    function liveScene(reading) {
        if (!reading) return sceneFromClock(new Date().getHours());
        // Near the poles a day can have no sunrise or sunset at all.
        if (reading.sunrise == null || reading.sunset == null) return reading.isDay ? 'morning' : 'night';
        return sceneFromSun(placeMinutes(reading.utcOffset), reading.sunrise, reading.sunset);
    }

    const sky = {
        prefs: loadPrefs(),
        reading: loadReading(),

        savePrefs() {
            write(PREFS_KEY, this.prefs);
        },

        saveReading(reading) {
            this.reading = reading;
            write(READING_KEY, reading);
        },

        // The time of day it really is at the place, whatever look is pinned.
        liveScene() {
            return liveScene(this.reading);
        },

        scene() {
            return this.prefs.look === 'auto' ? this.liveScene() : this.prefs.look;
        },

        apply() {
            root.dataset.theme = this.scene();
            root.dataset.weather = this.reading ? this.reading.weather : 'clear';
            root.dataset.weatherFx = this.prefs.effects ? 'on' : 'off';
        },

        placeMinutes,
    };

    sky.apply();
    window.MyVocabSky = sky;
})();
