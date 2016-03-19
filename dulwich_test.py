import os
from time import time

from dulwich.repo import Repo
from dulwich.objects import Blob, Tree, Commit
from dulwich import porcelain


NODE_TREE = 'tree'
NODE_BLOB = 'blob'


class GitFsError(Exception):
    pass


class GitFsBadNodeType(GitFsError):
    pass


def git_object_is_tree(obj):
    return isinstance(obj, Tree)


def git_object_is_blob(obj):
    return isinstance(obj, Blob)


def git_ls_nodes(repo, tree, filepath=''):
    path = os.path.normpath(filepath)
    path = path.split(os.sep)[:-1]
    for i, x in enumerate(path):
        if not isinstance(tree, Tree):
            raise GitFsBadNodeType("Not folder: %s" % os.sep.join(path[:i]))
        _mode, subtree_sha = tree[x]
        tree = repo[subtree_sha]
    return tree.iteritems()


def git_object_to_odb(repo, git_object):
    return repo.object_store.add_object(git_object)


class Node(object):
    node_type = None

    def __init__(self, name, parent_node, repo, git_object=None):
        self.repo = repo
        self.parent_node = parent_node
        self.git_object = git_object
        self.name = name
        self.sha_on_create = git_object.id

    def __add_to_odb(self, git_object):
        return git_object_to_odb(self.repo, git_object)

    def save(self, mode=None):
        if self.git_object.id == self.sha_on_create:
            return False

        self.__add_to_odb(self.git_object)

        if self.parent_node:
            if self.node_type == NODE_TREE:
                mode = mode or 040000
            else:
                mode = mode or 0100644
            self.parent_node.add_git_node(self.name, mode, self.git_object)

        return True


class BlobNode(Node):
    node_type = NODE_BLOB

    def __init__(self, name, parent_node, repo, git_object=None):
        super(BlobNode, self).__init__(name, parent_node, repo, git_object)

    def read_data(self):
        return self.git_object.data

    def set_data(self, data):
        self.git_object = Blob.from_string(data)


class TreeNode(Node):
    node_type = NODE_TREE

    def __init__(self, name, parent_node, repo, git_object):
        super(TreeNode, self).__init__(name, parent_node, repo, git_object)

    def get_git_node(self, name):
        mode, sha1 = self.git_object[name]
        return mode, self.repo[sha1]

    def add_git_node(self, name, mode, git_object):
        self.git_object[name] = (mode, git_object.id)
        return True

    def get_node(self, name):
        _mode, git_object = self.get_git_node(name)
        if git_object_is_tree(git_object):
            return TreeNode(name, self, self.repo, git_object)
        return BlobNode(name, self, self.repo, git_object)

    def add_blobnode(self, name, content=None, mode=0100644):
        blob = BlobNode(name, self, self.repo, Blob())
        if not content is None:
            blob.set_data(content)
        self.add_git_node(name, mode, blob.git_object)
        return blob

    def add_treenode(self, name, mode=040000):
        tree = TreeNode(name, self, self.repo, Tree())
        self.add_git_node(name, mode, tree.git_object)
        return tree


    def nodes(self):
        nodes = git_ls_nodes(self.repo, self.git_object)
        gnodes = {}
        for node in nodes:
            sha1 = node.sha
            name = node.path
            git_object = self.repo[sha1]
            if git_object_is_tree(git_object):
                gnodes[name] = TreeNode(name, self, self.repo, git_object)
            else:
                gnodes[name] = BlobNode(name, self, self.repo, git_object)
        return gnodes


class Snapshot(object):
    def __init__(self, repo, ref='refs/heads/master'):
        self.repo = repo
        try:
            self.snapshot_commit = repo[ref]
            root_sha = self.snapshot_commit.tree
        except KeyError:
            self.snapshot_commit = None
            tree = Tree()
            git_object_to_odb(self.repo, tree)
            root_sha = tree.id

        self.ref = ref
        self.is_head = ref in repo.get_refs() or ref.startswith('refs/')
        self.root_node = TreeNode('/', None, repo, repo[root_sha])

    def root(self):
        return self.root_node

    def commit(self, name, email='example@example.com', message='wip', parents=None):
        if not self.is_head:
            return False

        # initial-commit
        if not self.snapshot_commit:
            parents = []
        elif not parents:
            parents = [self.snapshot_commit.id]

        if not self.snapshot_commit or self.root_node.git_object.id != self.snapshot_commit.tree:
            c = Commit()
            c.tree = self.root_node.git_object.id
            c.parents = parents
            c.author = c.committer = '%s <%s>' % (name.encode('utf-8'),
                                                  email.encode('utf-8'))
            c.commit_time = c.author_time = int(time())
            c.commit_timezone = c.author_timezone = 0
            c.encoding = "UTF-8"
            c.message = message
            self.repo.object_store.add_object(c)
            self.repo.refs[self.ref] = c.id
            return c
        return False


def example():
    print '=== Create folders and blobs ==='
    os.mkdir('git_test')
    repo = Repo.init('git_test')
    for x in range(5):
        r = Repo('git_test')
        s = Snapshot(r)

        root = s.root()
        print '$ ls'
        print root.nodes()
        dir1 = root.add_treenode('dir1')
        blob = dir1.add_blobnode('file1', 'content%s' % x)
        blob.save()

        dir2 = dir1.add_treenode('dir2')
        blob = dir2.add_blobnode('file2', 'content%s' % x)
        blob.save()
        dir2.save()

        dir1.save()
        root.save()

        print 'commit:', s.commit('testuser', message='test commit: %s' % x).id
        print '$ cat dir1/file1'
        print root.get_node('dir1').get_node('file1').read_data()
        print dir1.get_node('dir2').get_node('file2').read_data()
	print

    #Using Porcelain
    #Initiating a new repo
    repo = porcelain.init("myrepo")


    #cloning a repo from a server
    porcelain.clone("https://github.com/sugarlabs/browse-activity.git","browse_activity_clone")


    #local cloning
    porcelain.clone("/home/vikram/browse_activity_clone","browse_activity_clone_1")
    print
    print "Commiting"
    open("myrepo/testfile","w").write("data")
    porcelain.add(repo,"myrepo/testfile")
    porcelain.commit(repo,"A sample commit")

    open("myrepo/testfile","w").write("data1")
    porcelain.add(repo,"myrepo/testfile")
    porcelain.commit(repo,"Second commit")

    open("myrepo/testfile1","w").write("sugar-labs")
    porcelain.add(repo,"myrepo/testfile1")
    porcelain.commit(repo,"First commit")
    
    print "Commit Logs:"
    print porcelain.log(repo)

if __name__ == '__main__':
    example()
