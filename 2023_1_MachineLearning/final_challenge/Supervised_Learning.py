import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
from torchvision import models
import torch.optim as optim

import os
from PIL import Image
import argparse
  
import random
seed = 2023
random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True


class CustomDataset(Dataset):
    def __init__(self, root, transform=None):
        self.root = root
        self.transform = transform
        self.classes = os.listdir(root)
        self.class_to_idx = {c: int(c) for i, c in enumerate(self.classes)}
        self.imgs = []
        for c in self.classes:
            class_dir = os.path.join(root, c)
            for filename in os.listdir(class_dir):
                path = os.path.join(class_dir, filename)
                self.imgs.append((path, self.class_to_idx[c])) 
    def __len__(self):
        return len(self.imgs)
    def __getitem__(self, index):
        path, target = self.imgs[index]
        img = Image.open(path).convert('RGB')
        if self.transform is not None:
            img = self.transform(img)
        return img, target




####################
#If you want to use your own custom model
#Write your code here
####################
class Custom_model(nn.Module):
    def __init__(self):
        super(Custom_model, self).__init__()
        model = models.resnet18(weights='IMAGENET1K_V1')
        model.layer4 = Identity()
        model.fc = nn.Linear(256, 50)
        self.resnet = model

        model = models.mobilenet_v2(weights='IMAGENET1K_V2')
        model.classifier = nn.Sequential(nn.Linear(in_features=1280, out_features=50, bias=True))
        self.mobilenet = model

        self.models = [self.resnet, self.mobilenet]

    def forward(self, input):
        outputs = []
        for model in self.models:
            outputs.append(model(input))
        return sum(outputs) / len(outputs)
    
    def train(self, mode: bool = True):
        super().train(mode=mode)
        for model in self.models:
            model.train(mode=mode)



class Identity(nn.Module):
    def __init__(self):
        super(Identity, self).__init__()
    def forward(self, x):
        return x

####################
#Modify your code here
####################
def model_selection(selection):
    if selection == "resnet":
        model = models.resnet18(weights='IMAGENET1K_V1')
        model.conv1 =  nn.Conv2d(3, 64, kernel_size=3,stride=1, padding=1, bias=False)
        model.layer4 = Identity()
        model.fc = nn.Linear(256, 50)
    elif selection == "vgg":
        model = models.vgg11_bn(weights='IMAGENET1K_V1')
        model.features = nn.Sequential(*list(model.features.children())[:-7])
        model.classifier = nn.Sequential( nn.Linear(in_features=25088, out_features=50, bias=True))
    elif selection == "mobilenet":
        model = models.mobilenet_v2(weights='IMAGENET1K_V2')
        model.classifier = nn.Sequential(nn.Linear(in_features=1280, out_features=50, bias=True))
    elif  selection =='custom':
        model = Custom_model()
    return model



def train(net1, labeled_loader, optimizer, criterion):
    optimizer_mob, optimizer_res = optimizer

    total_loss_mob = 0
    total_loss_res = 0

    running_corrects_mob = 0
    running_corrects_res = 0

    running_total = 0

    net1.train()
    #Supervised_training
    for batch_idx, (inputs, targets) in enumerate(labeled_loader):
        if torch.cuda.is_available():
            inputs, targets = inputs.cuda(), targets.cuda()
        optimizer_mob.zero_grad()
        optimizer_res.zero_grad()

        with torch.set_grad_enabled(True):
            outputs_mob = net1.mobilenet(inputs)
            outputs_res = net1.resnet(inputs)

            _, predicted_mob = outputs_mob.max(1)
            _, predicted_res = outputs_res.max(1)

            running_corrects_mob += predicted_mob.eq(targets).sum().item()
            running_corrects_res += predicted_res.eq(targets).sum().item()

            loss_mob = criterion(outputs_mob, targets)
            loss_res = criterion(outputs_res, targets)

            loss_mob.backward()
            loss_res.backward()

            total_loss_mob += loss_mob
            total_loss_res += loss_res

            running_total += targets.size(0)

            optimizer_mob.step()
            optimizer_res.step()

    print(f"[loss_mob={total_loss_mob:.2f}, loss_res={total_loss_res:.2f}, score_mob={100. * running_corrects_mob / running_total : .2f}, score_res={100. * running_corrects_res / running_total : .2f}]")
        
        


        
def test(net, testloader):
    net.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for batch_idx, (inputs, targets) in enumerate(testloader):
            if torch.cuda.is_available():
                inputs, targets = inputs.cuda(), targets.cuda()
            outputs = net(inputs)
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
        return 100. * correct / total







if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--test',  type=str,  default='False')
    parser.add_argument('--student_abs_path',  type=str,  default='./')
    args = parser.parse_args()



    if not os.path.exists(os.path.join(args.student_abs_path, 'logs', 'Supervised_Learning')):
        os.makedirs(os.path.join(args.student_abs_path, 'logs', 'Supervised_Learning'))



    batch_size = 16 #Input the number of batch size
    print(f"batch size = {batch_size}")
    if args.test == 'False':
        train_transform = transforms.Compose([
                    transforms.RandomResizedCrop(64, scale=(0.2, 1.0)),
                    transforms.RandomHorizontalFlip(),
                    transforms.ToTensor(),
                    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
                ])
        test_transform = transforms.Compose([
                    transforms.ToTensor(),
                    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
                ])
        
        dataset = CustomDataset(root = './data/Supervised_Learning/labeled', transform = train_transform)
        labeled_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=4, pin_memory=True)
        
        dataset = CustomDataset(root = './data/Supervised_Learning/val', transform = test_transform)
        val_loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    else :
        test_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])
        

    model_name = "custom" #Input model name to use in the model_section class
                 #e.g., 'resnet', 'vgg', 'mobilenet', 'custom'
    print(f"model_name : {model_name}")

    if torch.cuda.is_available():
        model = model_selection(model_name).cuda()
    else :
        model = model_selection(model_name)

    params = sum(p.numel() for p in model.parameters() if p.requires_grad) / 1e6

    #You may want to write a loader code that loads the model state to continue the learning process
    #Since this learning process may take a while.
    
    
    if torch.cuda.is_available():
        criterion = nn.CrossEntropyLoss().cuda()
    else :
        criterion = nn.CrossEntropyLoss()
    
    epoch = 100
    optimizer_mobilenet = optim.Adam(model.mobilenet.parameters(), lr= 0.0001)
    scheduler_mobilenet = optim.lr_scheduler.LambdaLR(optimizer=optimizer_mobilenet,
                                            lr_lambda=lambda epoch: 0.93 ** epoch,
                                            last_epoch=-1,
                                            verbose=False)
    
    optimizer_resnet = optim.Adam(model.resnet.parameters(), lr= 0.00015)
    scheduler_resnet = optim.lr_scheduler.LambdaLR(optimizer=optimizer_resnet,
                                            lr_lambda=lambda epoch: 0.93 ** epoch,
                                            last_epoch=-1,
                                            verbose=False)
    
    best_result = 0
    if args.test == 'False':
        assert params < 7.0, "Exceed the limit on the number of model parameters" 
        for e in range(0, epoch):
            train(model, labeled_loader, (optimizer_mobilenet, optimizer_resnet), criterion)
            scheduler_mobilenet.step()
            scheduler_resnet.step()
            print(f"[val_score_mob={test(model.mobilenet, val_loader)}, val_score_res={test(model.resnet, val_loader)}]")
            tmp_res = test(model, val_loader)
            # You can change the saving strategy, but you can't change the file name/path
            # If there's any difference to the file name/path, it will not be evaluated.
            print('{}th performance, res : {}'.format(e, tmp_res))
            if best_result < tmp_res:
                best_result = tmp_res
                torch.save(model.state_dict(),  os.path.join('./logs', 'Supervised_Learning', 'best_model.pt'))
        print('Final performance {} - {}', best_result, params)
            
            
        
    else:
        #This part is used to evaluate. 
        #Do not edit this part!
        dataset = CustomDataset(root = '/data/23_1_ML_challenge/Supervised_Learning/test', transform = test_transform)
        test_loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

        model.load_state_dict(torch.load(os.path.join(args.student_abs_path, 'logs', 'Supervised_Learning', 'best_model.pt'), map_location=torch.device('cuda')))
        res = test(model, test_loader)
        print(res, ' - ' , params)
    
