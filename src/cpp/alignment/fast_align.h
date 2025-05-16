#pragma once

#include <vector>
#include <array>
#include <string>
#include <functional>
#include <memory>
#include <chrono>
#include <optional>
#include <mutex>
#include <thread> // For std::this_thread for potential sleep_for if needed by callbacks

// Forward declaration if Point3D is in a common types header
// struct Point3D;

namespace OpenManufacturing {
namespace Alignment {

struct Point3D {
    double x;
    double y;
    double z;
};

struct AlignmentResult {
    bool success;
    Point3D final_position;
    double optical_power_dbm;
    std::chrono::milliseconds elapsed_time;
    int iterations;
    std::vector<Point3D> trajectory;
    std::string error_message;
};

// Callback function types
// OpticalPowerCallback: Returns current optical power in dBm.
using OpticalPowerCallback = std::function<double()>;
// MotionCallback: Moves to target Point3D, returns true on success, false on failure.
using MotionCallback = std::function<bool(const Point3D& target_position)>;
// CheckStopCallback: Returns true if alignment should stop, false otherwise.
using CheckStopCallback = std::function<bool()>;

class FastAlignmentEngine {
public:
    FastAlignmentEngine(
        OpticalPowerCallback power_callback,
        MotionCallback motion_callback,
        CheckStopCallback stop_callback, // Added stop callback
        double position_tolerance_um = 0.05,
        double optical_threshold_dbm = -3.0,
        int max_iterations = 100
    );
    
    ~FastAlignmentEngine();
    
    AlignmentResult alignGradientDescent(
        const Point3D& start_position,
        double initial_step_size_um = 0.5,
        double step_reduction_factor = 0.5,
        int max_step_reductions = 5,
        double gradient_diff_step_um = 0.1 // Step for numerical gradient calculation
    );
    
    AlignmentResult alignSpiralSearch(
        const Point3D& center_xy_start_z, // Center in XY, starting Z for spiral plane
        double max_radius_um = 10.0,
        double spiral_step_density = 1.0, // Controls how dense the spiral points are
        int points_per_revolution = 16,
        double z_search_range_um = 5.0, // Search +/- this range in Z
        double z_search_step_um = 0.5
    );
    
    AlignmentResult alignCombined(
        const Point3D& start_position,
        double spiral_max_radius_um = 10.0,
        double spiral_step_density = 1.0, // Pass through to spiral search
        double descent_initial_step_um = 0.2,
        double descent_gradient_diff_step_um = 0.05 // Pass through to gradient descent
    );
    
    // void requestStopAlignment(); // Stop is now handled by stop_callback
    
    void setParameters(
        double position_tolerance_um,
        double optical_threshold_dbm,
        int max_iterations
    );

private:
    // PImpl idiom: private implementation details
    struct Impl;
    std::unique_ptr<Impl> pImpl;
    
    // Helper methods, can be moved to Impl if they don't need direct FastAlignmentEngine state
    Point3D computeGradientNumerically(const Point3D& current_position, double diff_step_size);
    // double measureOpticalPower(); // Delegated to pImpl which calls callback
    // bool moveToPosition(const Point3D& position); // Delegated to pImpl
};

} // namespace Alignment
} // namespace OpenManufacturing 