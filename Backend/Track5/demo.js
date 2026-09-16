/**
 * Demo application for Track 5 trajectory and traffic analytics.
 *
 * This demonstrates the core functionality of trajectory analysis,
 * including validation, distance calculations, and road segment mapping.
 */

import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import {
  haversineKm,
  validateEvent,
  point,
  mapMatch,
} from "./trajectory.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Load JSON data from file.
 * @param {string} filename
 * @returns {*}
 */
function loadJsonFile(filename) {
  const filePath = join(__dirname, filename);
  const data = readFileSync(filePath, "utf-8");
  return JSON.parse(data);
}

/**
 * Main demo function.
 */
function main() {
  console.log("=== Track 5 Analytics Demo ===\n");

  // Load data
  const vehicleEvents = loadJsonFile("dummy_vehicle_events.json");
  const roadSegments = loadJsonFile("dummy_road_segments.json");

  console.log(`Loaded ${vehicleEvents.length} vehicle events`);
  console.log(`Loaded ${roadSegments.length} road segments\n`);

  // Process each event
  console.log("--- Processing Vehicle Events ---");
  const trajectories = {};

  for (const event of vehicleEvents) {
    try {
      // Validate event
      validateEvent(event);

      // Convert to point
      const pt = point(event);

      // Map to nearest road segment
      const roadInfo = mapMatch(pt, roadSegments);

      // Store in trajectory
      if (!trajectories[event.vehicle_id]) {
        trajectories[event.vehicle_id] = [];
      }

      trajectories[event.vehicle_id].push({
        ...pt,
        ...roadInfo,
      });

      console.log(
        `✓ Vehicle ${event.vehicle_id}: ${pt.latitude}, ${pt.longitude} -> ${roadInfo.road_segment_id || "No match"}`
      );
    } catch (error) {
      console.error(
        `✗ Error processing event for vehicle ${event.vehicle_id}: ${error.message}`
      );
    }
  }

  // Calculate distances between consecutive points
  console.log("\n--- Distance Calculations ---");
  for (const [vehicleId, points] of Object.entries(trajectories)) {
    if (points.length > 1) {
      console.log(`\nVehicle ${vehicleId}:`);
      let totalDistance = 0;

      for (let i = 1; i < points.length; i++) {
        const distance = haversineKm(points[i - 1], points[i]);
        totalDistance += distance;
        console.log(`  Point ${i - 1} → ${i}: ${distance.toFixed(3)} km`);
      }

      console.log(`  Total distance: ${totalDistance.toFixed(3)} km`);
    }
  }

  // Summary statistics
  console.log("\n--- Summary ---");
  console.log(`Total trajectories: ${Object.keys(trajectories).length}`);
  for (const [vehicleId, points] of Object.entries(trajectories)) {
    console.log(`  ${vehicleId}: ${points.length} points`);
  }
}

// Run the demo
main();
