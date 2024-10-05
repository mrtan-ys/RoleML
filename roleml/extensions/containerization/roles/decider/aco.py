from datetime import datetime
from typing import Literal, Optional
import numpy as np
import matplotlib.pyplot as plt
import concurrent.futures


class AntColonyOptimizer:
    def __init__(
        self,
        task_req: np.ndarray,
        host_cap: np.ndarray,
        trans_time: np.ndarray,
        task_src: np.ndarray,
    ) -> None:
        """
        :param task_req: 任务所需计算资源，shape=(任务数量, 资源数量)
        :param host_cap: 设备计算能力，shape=(设备数量, 资源数量)
        :param trans_time: 任务分配到设备上所需传输时间，shape=(任务数量, 设备数量)
        :param task_src: 任务原本所在的设备，shape=(任务数量)
        """

        # 参数设置
        # self.m = 10  # 任务数
        # self.n = 5  # 设备数
        # self.w: np.ndarray = np.random.randint(1, 10, size=self.m)  # 任务所需计算资源
        # self.c: np.ndarray = np.random.randint(10, 30, size=self.n)  # 设备计算能力
        # self.t = np.random.randint(1, 10, size=(self.m, self.n))  # 任务分配到设备上所需传输时间
        self.task_src = task_src  # 任务原本所在的设备

        self.m = task_req.shape[0]  # 任务数
        self.n = host_cap.shape[0]  # 设备数
        self.w: np.ndarray = task_req  # 任务所需计算资源
        self.c: np.ndarray = host_cap  # 设备计算能力
        self.t = trans_time  # 任务分配到设备上所需传输时间
        self.pheromone = np.ones((self.m, self.n))  # 信息素矩阵
        self.stop_iter = 10  # 连续多少代最优解不变时停止搜索
        
        self.ants_num = 50  # 蚂蚁数量
        self.max_iter = 100  # 最大迭代次数
        self.alpha = 1.0  # 信息素重要程度因子
        self.beta = 2.0  # 启发函数重要程度因子
        self.rho = 0.5  # 信息素挥发因子
        self.q = 100  # 信息素强度常数

    # 启发函数，计算蚂蚁从第i个任务移动到第j个设备的吸引程度
    def heuristic_func(self, i: int, j: int):
        if self.t[i][j] == np.inf:
            return 0
        return 1.0 / self.t[i][j]

    # 选择下一个任务和设备
    def select_next(self, ant_i: int, task_i: int, resource_left: np.ndarray):
        available_devices = []
        for j in range(self.n):
            if (self.w[task_i] <= resource_left[j]).all():
                available_devices.append(j)
        if len(available_devices) == 0:
            return None  # 没有可用设备，搜索失败
        
        # if ant_i > self.ants_num * 0.5:
        #     return np.random.choice(available_devices)

        probs = np.zeros(len(available_devices))  # 选择概率
        for i, j in enumerate(available_devices):
            probs[i] = (
                self.pheromone[task_i][j] ** self.alpha
                * self.heuristic_func(task_i, j) ** self.beta
            )
        probs /= np.sum(probs)
        next_device = np.random.choice(available_devices, p=probs)
        return next_device

    # 更新信息素
    def update_pheromone(self, delta_pheromone: np.ndarray):
        self.pheromone *= 1 - self.rho
        self.pheromone += delta_pheromone

    # 蚁群算法主函数
    def ant_colony_optimization(self):
        best_cost = float("inf")
        best_solution = None

        stop_count = 0

        history = {}

        t = datetime.now()

        for iteration in range(self.max_iter):
            t2 = datetime.now()

            iter_best_cost = float("inf")
            iter_best_solution = None

            # 初始化蚂蚁
            ants = np.ndarray((self.ants_num, self.m), dtype=int) * -1

            # 搜索解决方案
            for ant_i in range(self.ants_num):
                resource_left = np.copy(self.c)
                for i in range(self.m):
                    task = i
                    device = self.select_next(ant_i, task, resource_left)
                    if device is None:
                        break
                    ants[ant_i][task] = device
                    resource_left[device] -= self.w[task]

            delta_pheromone = np.zeros((self.m, self.n))
            for ant_i in range(self.ants_num):
                if ants[ant_i][-1] == -1:
                    continue  # 搜索失败，没有分配到所有任务
                # 计算解决方案的花费
                link_trans_time: dict[tuple[int, int], float] = {}
                for i in range(self.m):
                    dst_idx = ants[ant_i][i]
                    src_idx = self.task_src[i]
                    time = self.t[i][dst_idx]
                    link_trans_time.setdefault((src_idx, dst_idx), 0)
                    link_trans_time[(src_idx, dst_idx)] += time

                cost = max(link_trans_time.values())

                # 更新最佳解决方案
                if cost < iter_best_cost:
                    iter_best_cost = cost
                    iter_best_solution = ants[ant_i]

                # 更新信息素
                for i, j in enumerate(ants[ant_i]):
                    delta_pheromone[i][j] += self.q / cost

                history.setdefault(iteration, [])
                history[iteration].append(cost)

            self.update_pheromone(delta_pheromone)

            # 更新最佳解决方案
            if iter_best_cost < best_cost:
                best_cost = iter_best_cost
                best_solution = iter_best_solution
                stop_count = 0
            else:
                stop_count += 1

            if stop_count >= self.stop_iter:
                break

            print(f"第{iteration}代 Time: {datetime.now() - t2}")
            

        print(f"Time: {datetime.now() - t}, Best Cost: {best_cost},")

        for x, ys in history.items():
            for y in ys:
                plt.scatter(x, y, color='blue', s=2)
        plt.show()

        return best_solution, best_cost
    
    def _ant_worker(self, ant_i: int):
        resource_left = np.copy(self.c)
        solution = np.ndarray(self.m, dtype=int) * -1
        for i in range(self.m):
            task = i
            device = self.select_next(ant_i, task, resource_left)
            if device is None:
                break
            solution[task] = device
            resource_left[device] -= self.w[task]

        delta_pheromone = np.zeros((self.m, self.n))
        cost = -1
        if solution[-1] != -1:
            link_trans_time: dict[tuple[int, int], float] = {}
            for i in range(self.m):
                dst_idx = solution[i]
                src_idx = self.task_src[i]
                time = self.t[i][dst_idx]
                link_trans_time.setdefault((src_idx, dst_idx), 0)
                link_trans_time[(src_idx, dst_idx)] += time

            cost = max(link_trans_time.values())

            for i, j in enumerate(solution):
                delta_pheromone[i][j] += self.q / cost

        return solution, cost, delta_pheromone
    
    def ant_colony_optimization_parallel(self):
        best_cost = float("inf")
        best_solution = None

        stop_count = 0

        history = {}

        t = datetime.now()

        for iteration in range(self.max_iter):
            t2 = datetime.now()

            iter_best_cost = float("inf")
            iter_best_solution = None

            # # 初始化蚂蚁
            # ants = np.ndarray((self.ants_num, self.m), dtype=int) * -1

            # 搜索解决方案
            iter_delta_pheromone = np.zeros((self.m, self.n))
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = [executor.submit(self._ant_worker, i) for i in range(self.ants_num)]
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    solution, cost, delta_pheromone = future.result()
                    # ants[i] = solution
                    if cost != -1 and cost < iter_best_cost:
                        iter_best_cost = cost
                        iter_best_solution = solution
                    iter_delta_pheromone += delta_pheromone

                    history.setdefault(iteration, [])
                    history[iteration].append(cost)

            self.update_pheromone(iter_delta_pheromone)
            
            # 更新最佳解决方案
            if iter_best_cost < best_cost:
                best_cost = iter_best_cost
                best_solution = iter_best_solution
                stop_count = 0
            else:
                stop_count += 1

            if stop_count >= self.stop_iter:
                break

            print(f"第{iteration}代 Time: {datetime.now() - t2}")


        print(f"Time: {datetime.now() - t}, Best Cost: {best_cost},")

        for x, ys in history.items():
            for y in ys:
                plt.scatter(x, y, color='blue', s=2)
        plt.show()

        return best_solution, best_cost