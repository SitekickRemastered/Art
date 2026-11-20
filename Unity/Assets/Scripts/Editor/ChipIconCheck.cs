#if UNITY_EDITOR
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
	/// Builds the gallery's grid in the editor and reports what each cell is, then
	/// renders the top of the grid to Logs/pilot/icons.png so the vector icons can
	/// be looked at without pressing play.
	///
	/// The cells are ChipIconGraphic drawing the chip's own SVG sprite mesh through
	/// Assets/Materials/ChipIcon.mat; the point of the picture is to show that the
	/// cells are vector meshes with their gradients resolved, which a baked PNG
	/// used to stand in for.
	/// </summary>
	public static class ChipIconCheck
	{
		public const string ReportPath = "Logs/pilot/icons.txt";
		public const string ShotPath = "Logs/pilot/icons.png";

		[MenuItem( "Sitekick/Check Chip Icons" )]
		public static void Run()
		{
			EditorSceneManager.OpenScene( ChipMovieCheck.ScenePath, OpenSceneMode.Single );
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			var camera = Camera.main;
			if ( gallery == null || camera == null )
			{
				Debug.LogError( "gallery scene is missing the gallery or camera" );
				return;
			}

			gallery.Build();

			var lines = new StringBuilder();
			Transform content = null;
			foreach ( var t in Object.FindObjectsByType<Transform>( FindObjectsSortMode.None ) )
				if ( t.name == "Content" && t.childCount > 1 )
					content = t;

			if ( content == null )
			{
				File.WriteAllText( ReportPath, "no grid content found\n" );
				Debug.LogError( "no grid content found" );
				return;
			}

			int svg = 0, plain = 0, missing = 0, noMaterial = 0;
			lines.AppendLine( "entries " + gallery.EntryCount + "  cells " + content.childCount );
			for ( int i = 0; i < content.childCount; i++ )
			{
				var cell = content.GetChild( i );
				var image = cell.GetComponent<Graphic>();
				if ( image is ChipIconGraphic )
					svg++;
				else if ( image is Image )
					plain++;

				var sprite = ( image as ChipIconGraphic ) != null ? ( (ChipIconGraphic) image ).sprite : null;
				if ( sprite == null )
					missing++;
				else
				{
					if ( sprite.vertices == null || sprite.vertices.Length == 0 )
						lines.AppendLine( "  " + cell.name + " sprite " + sprite.name + " has no mesh" );
					if ( !HasIconMaterial( image ) )
						noMaterial++;
				}

				if ( i < 8 )
					lines.AppendLine( "  " + cell.name + " " + ( image != null ? image.GetType().Name : "no graphic" )
						+ " sprite " + ( sprite != null ? sprite.name + " (" + sprite.vertices.Length + " verts)" : "none" )
						+ " material " + ( image != null && image.material != null ? image.material.name : "none" )
						+ " rect " + cell.GetComponent<RectTransform>().rect.size );
			}

			lines.AppendLine( "ChipIconGraphic " + svg + "  Image " + plain + "  no sprite " + missing + "  wrong material " + noMaterial );

			// Show it: the canvas is an overlay, so point it at the camera for one frame.
			var canvas = gallery.GetComponentInParent<Canvas>() ?? Object.FindFirstObjectByType<Canvas>();
			if ( canvas != null )
			{
				var mode = canvas.renderMode;
				var world = canvas.worldCamera;
				canvas.renderMode = RenderMode.ScreenSpaceCamera;
				canvas.worldCamera = camera;
				canvas.planeDistance = 5f;

				// top of the grid: the scroll view rests at its first row
				var scroll = gallery.GetComponentInParent<ScrollRect>() ?? Object.FindFirstObjectByType<ScrollRect>();
				if ( scroll != null )
					scroll.verticalNormalizedPosition = 1f;

				Capture( camera, ShotPath );

				canvas.renderMode = mode;
				canvas.worldCamera = world;
			}

			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );
		}

		static bool HasIconMaterial( Graphic image )
		{
			return image.material != null && image.material.name.StartsWith( "ChipIcon" );
		}

		static void Capture( Camera camera, string path )
		{
			const int w = 1440, h = 1080;
			var rt = new RenderTexture( w, h, 24, RenderTextureFormat.ARGB32 );
			var previous = camera.targetTexture;
			camera.targetTexture = rt;
			Canvas.ForceUpdateCanvases();
			camera.Render();
			camera.targetTexture = previous;
			var active = RenderTexture.active;
			RenderTexture.active = rt;
			var tex = new Texture2D( w, h, TextureFormat.RGB24, false );
			tex.ReadPixels( new Rect( 0, 0, w, h ), 0, 0 );
			tex.Apply();
			RenderTexture.active = active;
			Directory.CreateDirectory( Path.GetDirectoryName( path ) );
			File.WriteAllBytes( path, tex.EncodeToPNG() );
			Object.DestroyImmediate( tex );
			rt.Release();
			Object.DestroyImmediate( rt );
		}
	}
}
#endif
