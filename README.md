### 🏗 **Distributed Formation Control and Collision Avoidance via Barrier Functions for Multi-Agent Systems**  

## 🚀 **Overview**  
Multi-robot systems (MRS) play a crucial role in large-scale tasks such as **disaster response, material transport, and warehouse management**. However, ensuring **robust formation control** while avoiding collisions in **dynamic environments** is a significant challenge.  

This project introduces a **distributed formation control framework** that integrates **neural network-based control barrier functions (CBFs)** to enhance **scalability, robustness, and safety**. Unlike traditional handcrafted constraints, our approach learns safety constraints adaptively, enabling better performance in **nonlinear, large-scale multi-agent systems**.  

## 🎯 **Key Features**  
✅ **Collision-Free Formation Control** – Ensures safety and stability in dynamic environments.  
✅ **Neural Network-Based CBFs** – Eliminates the need for handcrafted safety constraints.  
✅ **Scalable to Large Multi-Agent Systems** – Adaptable to real-world applications.  
✅ **Handles Dynamic Obstacles** – Adjusts to environmental disturbances.  
✅ **Efficient Deployment** – Suitable for various multi-robot applications.  

## 🛠 **Installation**  
Clone the repository and install dependencies:  
```bash
git clone https://github.com/QintongXie/CLF-CBF.git
pip install -r requirements.txt
```

## 🚀 **Usage**
Evaluate the pretrained neural network CBF and controller:  
```bash
cd cars 
python evaluate.py --num_agents 32 --model_path models/model_iter_9999 --vis 1
```
`--num_agents` defines the number of agents present in the environment. `--model_path` specifies the prefix for the pretrained neural network weights. By default, visualization is turned off and can be enabled by setting `--vis` to 1.
Train the neural network CBF and controller from scratch:
```bash
python train.py --num_agents 32
```

## 🤝 **Contributing**  
Contributions are welcome! To contribute:  
1. Fork the repository.  
2. Create a new branch (`git checkout -b feature-branch`).  
3. Commit your changes (`git commit -m "Add feature"`).  
4. Push the branch (`git push origin feature-branch`).  
5. Submit a **Pull Request** 🚀.  

## 📜 **License**  
This project is licensed under the MIT License.  

## 📬 **Contact**  
For inquiries or collaboration:  
- **Qintong Xie** – qintong.xie.th@dartmouth.edu  
- **GitHub** – QintongXie (https://github.com/QintongXie)  
