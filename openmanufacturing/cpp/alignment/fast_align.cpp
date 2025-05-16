#include "fast_align.h"
#include <iostream> // For debugging, remove in production if not needed
#include <cmath>    // For std::sqrt, std::cos, std::sin, std::abs, M_PI (if needed)
#include <algorithm>// For std::min, std::max
#include <vector>   // For trajectory
#include <limits>   // For std::numeric_limits

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace OpenManufacturing {
namespace Alignment {

// Define the private implementation structure (PImpl idiom)
struct FastAlignmentEngine::Impl {
    OpticalPowerCallback power_cb_;
    MotionCallback motion_cb_;
    CheckStopCallback stop_cb_;
    
    double position_tolerance_um_;
    double optical_threshold_dbm_;
    int max_iterations_;
    
    // Current state during an alignment operation (optional, could be local to methods)
    // Point3D current_best_pos_;
    // double current_best_power_;

    Impl(
        OpticalPowerCallback power_cb,
        MotionCallback motion_cb,
        CheckStopCallback stop_cb,
        double pos_tolerance_um,
        double optical_threshold,
        int max_iter
    ) : power_cb_(std::move(power_cb)), 
        motion_cb_(std::move(motion_cb)),
        stop_cb_(std::move(stop_cb)),
        position_tolerance_um_(pos_tolerance_um),
        optical_threshold_dbm_(optical_threshold),
        max_iterations_(max_iter) 
    {
        if (!power_cb_ || !motion_cb_ || !stop_cb_) {
            throw std::invalid_argument("Callbacks for power, motion, and stop check must be provided.");
        }
    }

    // Helper: Safely call motion callback
    bool moveTo(const Point3D& pos) {
        if (stop_cb_()) return false; // Check stop before moving
        return motion_cb_(pos);
    }

    // Helper: Safely call power callback
    double getPower() {
        // if (stop_cb_()) return -std::numeric_limits<double>::infinity(); // Or handle differently
        return power_cb_();
    }
};

// --- FastAlignmentEngine Constructor & Destructor ---
FastAlignmentEngine::FastAlignmentEngine(
    OpticalPowerCallback power_callback,
    MotionCallback motion_callback,
    CheckStopCallback stop_callback,
    double position_tolerance_um,
    double optical_threshold_dbm,
    int max_iterations
) : pImpl(std::make_unique<Impl>(
        std::move(power_callback), 
        std::move(motion_callback),
        std::move(stop_callback),
        position_tolerance_um, 
        optical_threshold_dbm, 
        max_iterations
    )) {}

FastAlignmentEngine::~FastAlignmentEngine() = default; // Default destructor for unique_ptr<Impl>

// --- Parameter Setter ---
void FastAlignmentEngine::setParameters(
    double position_tolerance_um,
    double optical_threshold_dbm,
    int max_iterations
) {
    pImpl->position_tolerance_um_ = position_tolerance_um;
    pImpl->optical_threshold_dbm_ = optical_threshold_dbm;
    pImpl->max_iterations_ = max_iterations;
}

// --- Numerical Gradient Calculation ---
Point3D FastAlignmentEngine::computeGradientNumerically(const Point3D& current_pos, double diff_step_um) {
    Point3D gradient = {0.0, 0.0, 0.0};
    double base_power = pImpl->getPower(); // Power at current_pos (already there or move to it first)

    const std::array<Point3D, 3> axes_deltas = {{ {diff_step_um, 0, 0}, {0, diff_step_um, 0}, {0, 0, diff_step_um} }};
    double* gradient_components[] = {&gradient.x, &gradient.y, &gradient.z};

    for (size_t i = 0; i < 3; ++i) {
        if (pImpl->stop_cb_()) break;

        Point3D pos_plus_h = current_pos;
        pos_plus_h.x += axes_deltas[i].x;
        pos_plus_h.y += axes_deltas[i].y;
        pos_plus_h.z += axes_deltas[i].z;

        if (!pImpl->moveTo(pos_plus_h)) {
            // Failed to move, cannot compute gradient for this axis, or treat as zero gradient
            *(gradient_components[i]) = 0.0; 
            pImpl->moveTo(current_pos); // Attempt to return
            continue;
        }
        double power_plus_h = pImpl->getPower();
        
        // Central difference would be better if affordable (another move):
        // Point3D pos_minus_h = {current_pos.x - axes_deltas[i].x, ...};
        // moveTo(pos_minus_h); double power_minus_h = getPower();
        // *(gradient_components[i]) = (power_plus_h - power_minus_h) / (2.0 * diff_step_um);

        // Forward difference for now:
        *(gradient_components[i]) = (power_plus_h - base_power) / diff_step_um;
    }
    
    // Important: Return to the original position after gradient calculation probes
    pImpl->moveTo(current_pos);
    return gradient;
}

// --- Gradient Descent Alignment Algorithm ---
AlignmentResult FastAlignmentEngine::alignGradientDescent(
    const Point3D& start_position,
    double initial_step_size_um,
    double step_reduction_factor,
    int max_step_reductions,
    double gradient_diff_step_um
) {
    AlignmentResult result;
    result.success = false;
    result.iterations = 0;
    auto S = std::chrono::high_resolution_clock::now();

    if (!pImpl->moveTo(start_position)) {
        result.error_message = "Failed to move to start position.";
        result.elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now() - S);
        return result;
    }
    result.trajectory.push_back(start_position);

    Point3D current_pos = start_position;
    double current_power = pImpl->getPower();
    Point3D best_pos = current_pos;
    double best_power = current_power;

    double step_size = initial_step_size_um;
    int step_reductions_count = 0;

    for (int iter = 0; iter < pImpl->max_iterations_; ++iter) {
        if (pImpl->stop_cb_()) {
            result.error_message = "Alignment stopped by callback.";
            break;
        }
        result.iterations = iter + 1;

        Point3D gradient = computeGradientNumerically(current_pos, gradient_diff_step_um);
        double grad_magnitude = std::sqrt(gradient.x * gradient.x + gradient.y * gradient.y + gradient.z * gradient.z);

        if (grad_magnitude < 1e-9) { // Gradient is essentially zero
            if (step_reductions_count < max_step_reductions) {
                step_size *= step_reduction_factor;
                step_reductions_count++;
                // std::cout << "Gradient too small, reducing step size to: " << step_size << std::endl;
                continue;
            }
            // std::cout << "Gradient too small and max step reductions reached." << std::endl;
            break; // Converged or stuck
        }

        Point3D next_pos;
        next_pos.x = current_pos.x + step_size * (gradient.x / grad_magnitude);
        next_pos.y = current_pos.y + step_size * (gradient.y / grad_magnitude);
        next_pos.z = current_pos.z + step_size * (gradient.z / grad_magnitude);

        if (!pImpl->moveTo(next_pos)) {
            result.error_message = "Motion failed during gradient step.";
            break;
        }
        result.trajectory.push_back(next_pos);
        double next_power = pImpl->getPower();

        if (next_power > current_power) {
            current_pos = next_pos;
            current_power = next_power;
            if (current_power > best_power) {
                best_power = current_power;
                best_pos = current_pos;
            }
            // Optional: Reset step_size or step_reductions_count if improvement is significant
        } else {
            // Power did not improve, reduce step size and try again from current_pos (or best_pos)
            if (step_reductions_count < max_step_reductions) {
                step_size *= step_reduction_factor;
                step_reductions_count++;
                pImpl->moveTo(current_pos); // return to current_pos before re-evaluating gradient with smaller step
                // std::cout << "No improvement, reducing step size to: " << step_size << std::endl;
            } else {
                // std::cout << "No improvement and max step reductions reached." << std::endl;
                pImpl->moveTo(current_pos); // ensure we are at the last good spot
                break;
            }
        }

        if (best_power >= pImpl->optical_threshold_dbm_) {
            // std::cout << "Optical threshold reached." << std::endl;
            break;
        }
        // Check position tolerance if applicable (e.g. if step_size becomes very small)
        if (step_size < pImpl->position_tolerance_um_ * 0.1) { // Heuristic for step size being too small
             //std::cout << "Step size too small, considering converged." << std::endl;
             break;
        }
    }

    pImpl->moveTo(best_pos); // Ensure final position is the best one found
    result.final_position = best_pos;
    result.optical_power_dbm = pImpl->getPower(); // Re-measure at best_pos
    result.success = result.optical_power_dbm >= pImpl->optical_threshold_dbm_;
    if (result.success && result.error_message.empty()) {
      // No specific error if success is true based on threshold
    } else if (result.error_message.empty()) {
        result.error_message = "Alignment finished but optical threshold not met.";
    }
    
    result.elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now() - S);
    return result;
}

// --- Spiral Search Alignment Algorithm ---
AlignmentResult FastAlignmentEngine::alignSpiralSearch(
    const Point3D& center_xy_start_z,
    double max_radius_um,
    double spiral_step_density,
    int points_per_revolution,
    double z_search_range_um,
    double z_search_step_um
) {
    AlignmentResult result;
    result.success = false;
    result.iterations = 0; // Iterations here might mean number of points visited
    auto S = std::chrono::high_resolution_clock::now();

    if (!pImpl->moveTo(center_xy_start_z)) {
        result.error_message = "Failed to move to spiral search start position.";
        result.elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now() - S);
        return result;
    }
    result.trajectory.push_back(center_xy_start_z);

    Point3D current_pos = center_xy_start_z;
    double current_power = pImpl->getPower();
    Point3D best_pos = current_pos;
    double best_power = current_power;
    int points_visited = 0;

    // XY Spiral Search
    double angle_step = 2 * M_PI / points_per_revolution;
    double current_radius = 0;
    double radius_increment = spiral_step_density; // Adjust this for how fast spiral expands

    while(current_radius <= max_radius_um) {
        if (pImpl->stop_cb_()) {
            result.error_message = "Alignment stopped during XY spiral.";
            goto end_spiral_search; // Use goto for early exit from nested loops
        }
        current_radius += radius_increment;
        for (int i = 0; i < points_per_revolution; ++i) {
            if (pImpl->stop_cb_()) {
                result.error_message = "Alignment stopped during XY spiral revolution.";
                goto end_spiral_search;
            }
            points_visited++;
            double angle = i * angle_step;
            Point3D next_pos;
            next_pos.x = center_xy_start_z.x + current_radius * std::cos(angle);
            next_pos.y = center_xy_start_z.y + current_radius * std::sin(angle);
            next_pos.z = center_xy_start_z.z; // Keep Z constant for XY spiral

            if (!pImpl->moveTo(next_pos)) {
                // Optionally log or skip this point
                continue;
            }
            result.trajectory.push_back(next_pos);
            double power_at_next_pos = pImpl->getPower();

            if (power_at_next_pos > best_power) {
                best_power = power_at_next_pos;
                best_pos = next_pos;
                if (best_power >= pImpl->optical_threshold_dbm_) {
                    result.error_message = "Optical threshold met during XY spiral.";
                    goto end_spiral_search;
                }
            }
        }
    }

    // Z Search at best XY found
    current_pos = best_pos; // Start Z search from the best XY
    if (!pImpl->moveTo(current_pos)) {
         result.error_message = "Failed to move to best XY for Z search.";
         goto end_spiral_search;
    }
    
    double z_start = current_pos.z - z_search_range_um;
    double z_end = current_pos.z + z_search_range_um;

    for (double z = z_start; z <= z_end; z += z_search_step_um) {
        if (pImpl->stop_cb_()) {
            result.error_message = "Alignment stopped during Z search.";
            goto end_spiral_search;
        }
        points_visited++;
        Point3D next_z_pos = {current_pos.x, current_pos.y, z};
        if (!pImpl->moveTo(next_z_pos)) {
            continue;
        }
        result.trajectory.push_back(next_z_pos);
        double power_at_z = pImpl->getPower();
        if (power_at_z > best_power) {
            best_power = power_at_z;
            best_pos = next_z_pos;
            if (best_power >= pImpl->optical_threshold_dbm_) {
                 result.error_message = "Optical threshold met during Z search.";
                 goto end_spiral_search;
            }
        }
    }

end_spiral_search:
    pImpl->moveTo(best_pos);
    result.final_position = best_pos;
    result.optical_power_dbm = pImpl->getPower(); // Re-measure
    result.success = result.optical_power_dbm >= pImpl->optical_threshold_dbm_;
    result.iterations = points_visited;
    if (result.success && result.error_message.empty()) { 
      // No error if successful by threshold
    } else if (result.error_message.empty()){
        result.error_message = "Spiral search finished, optical threshold not met.";
    }
    result.elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now() - S);
    return result;
}

// --- Combined Alignment Strategy ---
AlignmentResult FastAlignmentEngine::alignCombined(
    const Point3D& start_position,
    double spiral_max_radius_um,
    double spiral_step_density,
    double descent_initial_step_um,
    double descent_gradient_diff_step_um
) {
    // Step 1: Spiral Search for a good starting point
    // Using start_position for center_xy_start_z directly
    AlignmentResult spiral_res = alignSpiralSearch(start_position, spiral_max_radius_um, spiral_step_density);

    if (pImpl->stop_cb_()) {
        spiral_res.error_message = (spiral_res.error_message.empty() ? "" : spiral_res.error_message + " | ") + "Stopped after spiral search.";
        return spiral_res; // Return spiral result if stopped
    }

    // Step 2: Gradient Descent from the best point found by spiral search
    // A threshold can be used to decide if spiral search found a promising enough point
    double power_threshold_for_refinement = -20.0; // Example: dBm
    if (spiral_res.success || spiral_res.optical_power_dbm > power_threshold_for_refinement) {
        AlignmentResult descent_res = alignGradientDescent(
            spiral_res.final_position, 
            descent_initial_step_um, 
            0.5, // default step_reduction_factor
            5,   // default max_step_reductions
            descent_gradient_diff_step_um
        );
        
        // Combine results: use descent result as primary, but prepend spiral trajectory
        descent_res.trajectory.insert(descent_res.trajectory.begin(), 
                                      spiral_res.trajectory.begin(), 
                                      spiral_res.trajectory.end());
        descent_res.iterations += spiral_res.iterations; // Sum iterations
        
        // If descent failed but spiral was better, could revert, but typically descent should refine or match
        return descent_res;
    } else {
        // Spiral search did not find a good enough point, return its result
        spiral_res.error_message = (spiral_res.error_message.empty() ? "" : spiral_res.error_message + " | ") + "Spiral search found no promising region for refinement.";
        return spiral_res;
    }
}

} // namespace Alignment
} // namespace OpenManufacturing 