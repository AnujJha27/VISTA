#include "worker_pool.hpp"

#include <algorithm>

namespace proof_search {

unsigned default_worker_count() {
  const unsigned hardware = std::thread::hardware_concurrency();
  return hardware > 1 ? hardware - 1 : 1;
}

WorkerPool::WorkerPool(unsigned worker_count) {
  for (unsigned i = 0; i < worker_count; ++i) {
    workers_.emplace_back([this] {
      for (;;) {
        std::function<void()> job;
        {
          std::unique_lock<std::mutex> lock(mutex_);
          ready_.wait(lock, [this] { return stopping_ || !jobs_.empty(); });
          if (stopping_ && jobs_.empty()) return;
          job = std::move(jobs_.front());
          jobs_.pop();
        }
        job();
      }
    });
  }
}

WorkerPool::~WorkerPool() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    stopping_ = true;
  }
  ready_.notify_all();
  for (auto& worker : workers_) worker.join();
}

}  // namespace proof_search
