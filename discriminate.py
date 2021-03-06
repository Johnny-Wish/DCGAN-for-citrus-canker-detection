from __future__ import print_function
import argparse
import os
import random
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
#import torch.optim as optim
import torch.utils.data
import torchvision.datasets as dset
import torchvision.transforms as transforms
import torchvision.utils as vutils
from torch.autograd import Variable
import numpy as np
from models import _netD, weights_init


parser = argparse.ArgumentParser()
parser.add_argument('--dataset', required=True, help='cifar10 | lsun | imagenet | folder | lfw | fake')
parser.add_argument('--dataroot', required=True, help='path to dataset')
parser.add_argument('--workers', type=int, help='number of data loading workers', default=2)
parser.add_argument('--batchSize', type=int, default=64, help='input batch size')
parser.add_argument('--imageSize', type=int, default=64, help='the height / width of the input image to network')
parser.add_argument('--nz', type=int, default=100, help='size of the latent z vector')
parser.add_argument('--ngf', type=int, default=64)
parser.add_argument('--ndf', type=int, default=64)
parser.add_argument('--niter', type=int, default=25, help='number of epochs to train for')
parser.add_argument('--lr', type=float, default=0.0002, help='learning rate, default=0.0002')
parser.add_argument('--beta1', type=float, default=0.5, help='beta1 for adam, default=0.5')
parser.add_argument('--cuda', action='store_true', help='enables cuda')
parser.add_argument('--ngpu', type=int, default=1, help='number of GPUs to use')
parser.add_argument('--netD', required = True, help="path to netD to evaluate real samples")
parser.add_argument('--outf', default='.', help='folder to output images and model checkpoints')
parser.add_argument('--dropoutD', default=None, type=float, help='implements dropout in netD')
parser.add_argument('--dropoutG', default=None, type=float, help='implements dropout in netG')
parser.add_argument('--manualSeed', type=int, help='manual seed')
parser.add_argument('--eval', action='store_true', help='whether to set netD.eval() while evaluating')

opt = parser.parse_args()
print(opt)

try:
    os.makedirs(opt.outf)
    # os.makedirs(opt.outf+"/model")
except OSError:
    pass

if opt.manualSeed is None:
    opt.manualSeed = random.randint(1, 10000)
print("Random Seed: ", opt.manualSeed)
random.seed(opt.manualSeed)
torch.manual_seed(opt.manualSeed)
if opt.cuda:
    torch.cuda.manual_seed_all(opt.manualSeed)

cudnn.benchmark = True

if torch.cuda.is_available() and not opt.cuda:
    print("WARNING: You have a CUDA device, so you should probably run with --cuda")

if opt.dataset in ['imagenet', 'folder', 'lfw']:
    # folder dataset
    dataset = dset.ImageFolder(root=opt.dataroot,
                               transform=transforms.Compose([
                                   transforms.Scale(opt.imageSize),
                                   transforms.CenterCrop(opt.imageSize),
                                   transforms.ToTensor(),
                                   transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
                               ]))
elif opt.dataset == 'lsun':
    dataset = dset.LSUN(db_path=opt.dataroot, classes=['bedroom_train'],
                        transform=transforms.Compose([
                            transforms.Scale(opt.imageSize),
                            transforms.CenterCrop(opt.imageSize),
                            transforms.ToTensor(),
                            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
                        ]))
elif opt.dataset == 'cifar10':
    dataset = dset.CIFAR10(root=opt.dataroot, download=True,
                           transform=transforms.Compose([
                               transforms.Scale(opt.imageSize),
                               transforms.ToTensor(),
                               transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
                           ]))
elif opt.dataset == 'fake':
    dataset = dset.FakeData(image_size=(3, opt.imageSize, opt.imageSize),
                            transform=transforms.ToTensor())
assert dataset
dataloader = torch.utils.data.DataLoader(dataset, batch_size=opt.batchSize,
                                         shuffle=False, num_workers=int(opt.workers))

ngpu = int(opt.ngpu)
ndf = int(opt.ndf)
nc = 3

netD = _netD(ngpu, dropout=opt.dropoutD, ndf=ndf, nc=nc)
netD.apply(weights_init)
if opt.netD != '':
    netD.load_state_dict(torch.load(opt.netD))
if opt.eval:
    netD.eval() # This is important, since modules are initialized to train mode and will behave ill on dropout
    print("model D IS set to eval")
else:
    print("model D is NOT set to eval")
# and BN
print(netD)



label = torch.FloatTensor(opt.batchSize)
input = torch.FloatTensor(opt.batchSize, 3, opt.imageSize, opt.imageSize)
real_label = 1
fake_label = 0

if opt.cuda:
    netD.cuda()
    input, label = input.cuda(), label.cuda()

predictions = np.array([])
for i, data in enumerate(dataloader, 0):
    real_cpu, _ = data
    # real_cpu is an instance of torch.FloatTensor of size (batch_size, nc, W, H)
    # UNDERSCORE "_" is an instance of torch.LongTensor of size (batch_size,)
    batch_size = real_cpu.size(0)
    if opt.cuda:
        real_cpu = real_cpu.cuda()
    input.resize_as_(real_cpu).copy_(real_cpu)
    label.resize_(batch_size).fill_(real_label)
    inputv = Variable(input, requires_grad=False)
    labelv = Variable(label, requires_grad=False)

    output = netD(inputv)
    predictions = np.concatenate((predictions, output.data.cpu().numpy()))
    print(" output of batch %d generated" % i)

print("The shape of the pred vector is:", predictions.shape)
print("The median of predictions is:", np.median(predictions))
print("The mean of predictions is:", predictions.mean())
print("The std of predictions is:", predictions.std())
np.savetxt('/output/predictions.txt', predictions)
