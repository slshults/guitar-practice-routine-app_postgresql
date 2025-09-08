import { useState, useEffect } from 'react';
import { trackItemOperation, trackContentUpdate } from '../utils/analytics';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@ui/dialog';
import { Button } from '@ui/button';
import { Input } from '@ui/input';
import { Textarea } from '@ui/textarea';
import { Label } from '@ui/label';
import { Loader2, Book } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@ui/tooltip";

export const ItemEditor = ({ open, onOpenChange, item = null, onItemChange }) => {
  const [formData, setFormData] = useState({
    'C': '',
    'D': '',
    'E': 5,
    'F': '',
    'G': '',
    'H': '',
  });
  const [error, setError] = useState(null);
  const [isDirty, setIsDirty] = useState(false);

  // Clear error and load item data when modal opens
  useEffect(() => {
    if (open && item) {
      // If we have a complete item (with all fields), use it directly
      if (item['D'] !== undefined || item['H'] !== undefined) {
        setFormData({
          'C': item['C'] || '',
          'D': item['D'] || '',
          'E': item['E'] || 5,
          'F': item['F'] || '',
          'G': item['G'] || '',
          'H': item['H'] || '',
        });
        setError(null);
        setIsDirty(false);
      } else {
        // We have a lightweight item (only ID and Title), need to fetch full data
        fetchFullItemData(item['A']);
      }
    }
  }, [open, item]);

  const fetchFullItemData = async (itemId) => {
    try {
      const response = await fetch(`/api/items/${itemId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch item details');
      }
      const fullItem = await response.json();
      
      setFormData({
        'C': fullItem['C'] || '',
        'D': fullItem['D'] || '',
        'E': fullItem['E'] || 5,
        'F': fullItem['F'] || '',
        'G': fullItem['G'] || '',
        'H': fullItem['H'] || '',
      });
      setError(null);
      setIsDirty(false);
    } catch (err) {
      setError(`Failed to load item: ${err.message}`);
      console.error('Fetch item error:', err);
    }
  };

  const handleFormChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setIsDirty(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const { G: _G, ...dataToSend } = formData;
      
      // Ensure no trailing slash and handle empty item ID case
      const baseUrl = '/api/items';
      const url = item?.['A'] ? `${baseUrl}/${item['A']}` : baseUrl;
      
      const response = await fetch(url, {
        method: item ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(dataToSend),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.error || 'Failed to save item');
      }

      const savedItem = await response.json();
      
      // Track item creation or update
      const isCreating = !item?.['A'];
      const itemName = formData['C'] || 'Unnamed Item';
      
      if (isCreating) {
        trackItemOperation('created', 'item', itemName);
      } else {
        trackItemOperation('updated', 'item', itemName);
        
        // Track specific content updates if this is an edit
        const originalTitle = item?.['C'] || '';
        const originalNotes = item?.['D'] || '';
        const originalTuning = item?.['H'] || '';
        const originalSongbook = item?.['I'] || '';
        
        if (formData['D'] && formData['D'] !== originalNotes) {
          trackContentUpdate('notes', itemName);
        }
        if (formData['H'] && formData['H'] !== originalTuning) {
          trackContentUpdate('tuning', itemName);
        }
        if (formData['I'] && formData['I'] !== originalSongbook) {
          trackContentUpdate('folder_path', itemName);
        }
      }
      
      onItemChange?.(savedItem);
      onOpenChange(false);
    } catch (err) {
      setError(err.message);
      console.error('Save error:', err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-gray-800">
        <DialogHeader>
          <DialogTitle>
            {item ? `Edit Item: ${item['C']}` : 'Create New Item'}
          </DialogTitle>
          <DialogDescription>
            Edit the details of your practice item
          </DialogDescription>
          {error && (
            <div className="mt-2 text-sm text-red-500">
              {error}
            </div>
          )}
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={formData['C']}
              onChange={(e) => handleFormChange('C', e.target.value)}
              placeholder="Enter item title"
              required
              className="bg-gray-900 text-white"
              autocomplete="off"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="duration">Duration (minutes)</Label>
            <Input
              id="duration"
              type="number"
              min="1"
              value={formData['E']}
              onChange={(e) => handleFormChange('E', parseInt(e.target.value) || 5)}
              required
              className="bg-gray-900 text-white"
              autocomplete="off"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="songbook">Songbook Folder</Label>
            <Input
              id="songbook"
              value={formData['F']}
              onChange={(e) => handleFormChange('F', e.target.value)}
              placeholder="D:\Users\Steven\Documents\Guitar\Songbook\SongName"
              className="bg-gray-900 font-mono"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="tuning">Tuning</Label>
            <Input
              id="tuning"
              value={formData['H']}
              onChange={(e) => handleFormChange('H', e.target.value)}
              placeholder="e.g. EADGBE"
              className="bg-gray-900 text-white"
              autocomplete="off"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              value={formData['D']}
              onChange={(e) => handleFormChange('D', e.target.value)}
              placeholder="Enter any notes"
              className="h-24 bg-gray-900 text-white"
              autocomplete="off"
            />
          </div>

          <div className="flex justify-end space-x-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="text-gray-300 hover:text-white"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700"
              disabled={!isDirty}
            >
              Save
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export const BulkSongbookUpdate = ({ onComplete }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [paths, setPaths] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsUpdating(true);
    try {
      const response = await fetch('/api/items/update-songbook-paths', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          paths: paths.split('\n').filter(p => p.trim()),
        }),
      });

      const data = await response.json();
      if (response.ok) {
        setResult(data);
        onComplete?.();
      } else {
        throw new Error(data.error || 'Failed to update paths');
      }
    } catch (err) {
      console.error('Update error:', err);
      setResult({ error: err.message });
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsOpen(true)}
              className="text-gray-400 hover:text-gray-200"
            >
              <Book className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Bulk Update Songbook Paths</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-2xl bg-gray-800">
          <DialogHeader>
            <DialogTitle>Bulk Update Songbook Paths</DialogTitle>
            <DialogDescription>
              Paste your folder paths, one per line
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="paths">Folder Paths</Label>
              <Textarea
                id="paths"
                value={paths}
                onChange={(e) => setPaths(e.target.value)}
                placeholder="D:\Path\To\Songbook\Folder"
                className="h-64 bg-gray-900 text-white font-mono"
                disabled={isUpdating}
              />
            </div>

            {result && (
              <div className={`text-sm ${result.error ? 'text-red-500' : 'text-green-500'}`}>
                {result.error ? result.error : `Updated ${result.updated_count} items successfully!`}
              </div>
            )}

            <div className="flex justify-end space-x-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsOpen(false)}
                className="text-gray-300 hover:text-white"
                disabled={isUpdating}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700"
                disabled={isUpdating || !paths.trim()}
              >
                {isUpdating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Updating...
                  </>
                ) : (
                  'Update Paths'
                )}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ItemEditor; 