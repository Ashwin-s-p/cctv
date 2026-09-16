/**
 * Track 5 trajectory and traffic analytics.
 *
 * The module consumes vehicle_events JSON contract produced by Track 4.
 * It deliberately has no database, web framework, message broker, or frontend
 * dependencies so the data source can later be replaced by a Track 4 API client.
 */

/**
 * @typedef {Object} Event
 * @property {string} vehicle_id
 * @property {string} timestamp
 * @property {number} latitude
 * @property {number} longitude
 * @property {string} [camera_id]
 * @property {string} [road_segment_id]
 * @property {string} [area]
 */

/**
 * @typedef {Object} Point
 * @property {number} latitude
 * @property {number} longitude
 * @property {string} timestamp
 * @property {string} [camera_id]
 * @property {string} [road_segment_id]
 * @property {string} [area]
 */

/**
 * @typedef {Object} RoadSegment
 * @property {string} road_segment_id
 * @property {string} [road_name]
 * @property {string} [area]
 * @property {number} latitude
 * @property {number} longitude
 */

const EARTH_RADIUS_KM = 6371.0088;

/**
 * Parse and validate a numeric value.
 * @param {*} value
 * @param {string} field
 * @returns {number}
 * @throws {Error}
 */
function _number(value, field) {
  const num = parseFloat(value);
  if (isNaN(num)) {
    throw new Error(`${field} must be numeric`);
  }
  return num;
}

/**
 * Parse and validate an ISO-8601 timestamp.
 * @param {*} value
 * @returns {Date}
 * @throws {Error}
 */
function _timestamp(value) {
  if (typeof value !== "string") {
    throw new Error("timestamp must be an ISO-8601 string");
  }
  const normalized = value.replace("Z", "+00:00");
  const date = new Date(normalized);
  if (isNaN(date.getTime())) {
    throw new Error(`invalid timestamp: ${value}`);
  }
  return date;
}

/**
 * Return the great-circle distance between two latitude/longitude points in kilometers.
 * @param {Point} first
 * @param {Point} second
 * @returns {number}
 */
export function haversineKm(first, second) {
  const lat1 = (Math.PI / 180) * parseFloat(first.latitude);
  const lon1 = (Math.PI / 180) * parseFloat(first.longitude);
  const lat2 = (Math.PI / 180) * parseFloat(second.latitude);
  const lon2 = (Math.PI / 180) * parseFloat(second.longitude);

  const deltaLat = lat2 - lat1;
  const deltaLon = lon2 - lon1;

  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;

  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
}

/**
 * Validate that an event has all required fields with valid values.
 * @param {Event} event
 * @throws {Error}
 */
export function validateEvent(event) {
  const requiredFields = ["vehicle_id", "timestamp", "latitude", "longitude"];
  for (const field of requiredFields) {
    if (!(field in event)) {
      throw new Error(`vehicle event is missing required field: ${field}`);
    }
  }

  _timestamp(event.timestamp);
  const latitude = _number(event.latitude, "latitude");
  const longitude = _number(event.longitude, "longitude");

  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
    throw new Error("latitude/longitude is outside valid bounds");
  }
}

/**
 * Convert an event to a point object.
 * @param {Event} event
 * @returns {Point}
 */
export function point(event) {
  const result = {
    latitude: parseFloat(event.latitude),
    longitude: parseFloat(event.longitude),
    timestamp: event.timestamp,
  };

  const optionalFields = ["camera_id", "road_segment_id", "area"];
  for (const field of optionalFields) {
    if (event[field] != null) {
      result[field] = event[field];
    }
  }

  return result;
}

/**
 * Find the nearest road segment to a point using equirectangular distance.
 * @param {Point} pt
 * @param {RoadSegment[]} roadSegments
 * @returns {RoadSegment|null}
 */
function _nearestSegment(pt, roadSegments) {
  if (roadSegments.length === 0) {
    return null;
  }

  const latitude = parseFloat(pt.latitude);
  const longitude = parseFloat(pt.longitude);
  const scale = Math.cos((Math.PI / 180) * latitude);

  let nearest = roadSegments[0];
  let minDistance = Infinity;

  for (const segment of roadSegments) {
    const segmentLat = parseFloat(segment.latitude);
    const segmentLon = parseFloat(segment.longitude);
    const distance = Math.hypot(
      (longitude - segmentLon) * scale,
      latitude - segmentLat
    );

    if (distance < minDistance) {
      minDistance = distance;
      nearest = segment;
    }
  }

  return nearest;
}

/**
 * Attach the nearest supplied road segment to a trajectory point.
 * @param {Point} pt
 * @param {RoadSegment[]} roadSegments
 * @returns {Object}
 */
export function mapMatch(pt, roadSegments) {
  const segment = _nearestSegment(pt, roadSegments);

  if (segment === null) {
    return {};
  }

  const result = {
    road_segment_id: segment.road_segment_id,
  };

  if (segment.road_name) {
    result.road_name = segment.road_name;
  }

  if (segment.area) {
    result.area = segment.area;
  }

  return result;
}
