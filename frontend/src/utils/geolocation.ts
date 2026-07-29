/** Browser geolocation helper for Location Settings / setup. */

export interface BrowserCoordinates {
  latitude: number;
  longitude: number;
}

export class GeolocationDeniedError extends Error {
  constructor(message = "Location permission was denied.") {
    super(message);
    this.name = "GeolocationDeniedError";
  }
}

export class GeolocationUnavailableError extends Error {
  constructor(message = "Browser geolocation is not available.") {
    super(message);
    this.name = "GeolocationUnavailableError";
  }
}

export function detectBrowserLocation(timeoutMs: number = 10_000): Promise<BrowserCoordinates> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return Promise.reject(new GeolocationUnavailableError());
  }

  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          reject(new GeolocationDeniedError());
        } else {
          reject(new GeolocationUnavailableError(error.message || "Could not detect location."));
        }
      },
      { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 60_000 },
    );
  });
}
